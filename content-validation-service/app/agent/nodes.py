from __future__ import annotations
import base64
import hashlib
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict
from app.agent.state import ValidationGraphState
from app.agent.tools import (
    retrieve_piece_content,
    validate_legal_compliance,
    convert_html_to_image,
    validate_brand_compliance,
    validate_image_brand_compliance,
    fetch_channel_specs,
)
from app.core.validators import validate_piece_format_and_size, validate_piece_specs
from app.core.metrics import (
    NODE_DURATION,
    A2A_CALLS,
    A2A_DURATION,
    SPECS_RESULT,
    BRANDING_RESULT,
)

logger = logging.getLogger(__name__)

_DATA_URL_IMAGE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=]+$")
DEBUG_IMAGES_DIR = os.environ.get("DEBUG_IMAGES_DIR", "/app/debug_images")

def _save_debug_image(base64_image: str, image_format: str, piece_id: Any, campaign_id: Any) -> str | None:
    """Salva imagem convertida em pasta local para debug."""
    try:
        os.makedirs(DEBUG_IMAGES_DIR, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        ext = image_format.lower()
        filename = f"piece_{piece_id}_{campaign_id}_{timestamp}.{ext}"
        filepath = os.path.join(DEBUG_IMAGES_DIR, filename)
        
        image_bytes = base64.b64decode(base64_image)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        
        logger.info("Debug image saved: %s (%d bytes)", filepath, len(image_bytes))
        return filepath
    except Exception as e:
        logger.warning("Failed to save debug image: %s", e)
        return None


def _is_error_like_content(raw: str) -> bool:
    if not raw or len(raw.strip()) == 0:
        return True

    if _is_data_url_image(raw):
        return False
    strip = raw.strip()
    if strip.lower().startswith("<"):
        return False
    s = strip.lower()
    if s.startswith("error executing tool") or s.startswith("error "):
        return True
    if "error executing" in s or "traceback" in s:
        return True
    if "404" in s or "not found" in s:
        return True
    if "http/1.1" in s and ("404" in s or "500" in s):
        return True
    return False


def _is_data_url_image(raw: str) -> bool:
    """Verifica se string é data URL de imagem (data:image/<png|jpeg|...>;base64,...)."""
    return bool(_DATA_URL_IMAGE.match(raw.strip()))


def validate_channel_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    1) validate_channel: valida estrutura (canal, campos, tipos).
    
    - SMS/PUSH: campos existem e são do tipo certo → [specs, branding] em paralelo.
    - EMAIL/APP: canal reconhecido → retrieve_content.
    - Limites numéricos (chars, KB, pixels) ficam no validate_specs.
    """
    channel = (state.get("channel") or "").upper()
    content = state.get("content") or {}

    if channel not in ("SMS", "PUSH", "EMAIL", "APP"):
        return {
            "validation_result": {"valid": False, "message": f"Canal inválido: {channel}", "errors": [], "details": {}},
            "validation_valid": False,
        }

    if channel in ("SMS", "PUSH"):
        result = validate_piece_format_and_size(channel, content)
        valid = result.get("valid", False)
        out: Dict[str, Any] = {
            "validation_result": result,
            "validation_valid": valid,
        }
        if valid:
            out["content_for_compliance"] = content
        return out

    return {
        "validation_result": {"valid": True, "message": f"Canal {channel} -> retrieve_content", "errors": None, "details": {"channel": channel}},
        "validation_valid": True,
    }


async def retrieve_content_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    2) retrieve_content: chama campaigns-service (MCP).
    Sucesso -> validate_specs. Erro -> peça necessita aprovação humana.
    """
    channel = (state.get("channel") or "").upper()
    content = state.get("content") or {}

    campaign_id = content.get("campaign_id") or content.get("campaignId")
    piece_id = content.get("piece_id") or content.get("pieceId")
    commercial_space = content.get("commercial_space") or content.get("commercialSpace")

    if not campaign_id or not piece_id:
        return {
            "retrieve_ok": False,
            "retrieve_error": "Para EMAIL/APP, content deve ter campaign_id e piece_id.",
            "requires_human_approval": True,
            "human_approval_reason": "Falta campaign_id ou piece_id para buscar peça.",
        }
    if channel == "APP" and not commercial_space:
        return {
            "retrieve_ok": False,
            "retrieve_error": "Para APP, content deve ter commercial_space.",
            "requires_human_approval": True,
            "human_approval_reason": "Falta commercial_space para peça App.",
        }

    try:
        data = await retrieve_piece_content.ainvoke({
            "campaign_id": str(campaign_id),
            "piece_id": str(piece_id),
            "commercial_space": str(commercial_space) if commercial_space is not None else None,
        })
    except Exception as e:
        err = str(e)
        logger.warning("retrieve_content MCP error: %s", err)
        return {
            "retrieve_ok": False,
            "retrieve_error": err,
            "requires_human_approval": True,
            "human_approval_reason": f"Erro ao buscar peça via MCP: {err}",
        }

    raw = data.get("content", "")
    if not isinstance(raw, str):
        raw = str(raw) if raw is not None else ""

    if _is_error_like_content(raw):
        err = raw[:200] + ("..." if len(raw) > 200 else "")
        logger.warning("retrieve_content MCP returned error-like content: %s", err)
        return {
            "retrieve_ok": False,
            "retrieve_error": raw,
            "requires_human_approval": True,
            "human_approval_reason": f"Conteúdo da peça indisponível (MCP/campaigns): {err}",
        }

    retrieved_content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    html_for_branding = None
    image_for_branding = None
    conversion_metadata = None

    if channel == "APP":
        if not _is_data_url_image(raw):
            logger.warning("retrieve_content APP image is not a data URL: %.80s...", raw)
            return {
                "retrieve_ok": False,
                "retrieve_error": "Imagem App deve ser data URL (data:image/...;base64,...).",
                "requires_human_approval": True,
                "human_approval_reason": "Resposta do download da peça App inválida.",
            }
        content_for_compliance = {"image": raw}
        image_for_branding = raw
    elif channel == "EMAIL":
        try:
            logger.info("Converting EMAIL HTML to image for visual analysis...")
            conversion_result = await convert_html_to_image.ainvoke({
                "html_content": raw,
                "scale": 0.3,
                "image_format": "PNG",
            })
            
            if not conversion_result.get("success", False):
                error = conversion_result.get("error", "Unknown conversion error")
                logger.warning("HTML to image conversion failed: %s", error)
                return {
                    "retrieve_ok": False,
                    "retrieve_error": f"Falha ao converter HTML para imagem: {error}",
                    "requires_human_approval": True,
                    "human_approval_reason": f"Erro na conversão HTML->imagem: {error}",
                }
            
            base64_image = conversion_result.get("base64Image", "")
            image_format = conversion_result.get("imageFormat", "PNG").lower()
            data_url = f"data:image/{image_format};base64,{base64_image}"
            
            # Guarda metadados da conversão para validate_specs
            conversion_metadata = {
                "originalWidth": conversion_result.get("originalWidth", 0),
                "originalHeight": conversion_result.get("originalHeight", 0),
                "reducedWidth": conversion_result.get("reducedWidth", 0),
                "reducedHeight": conversion_result.get("reducedHeight", 0),
                "fileSizeBytes": conversion_result.get("fileSizeBytes", 0),
            }
            
            logger.info(
                "EMAIL HTML converted to image: %dx%d, %d bytes",
                conversion_metadata["reducedWidth"],
                conversion_metadata["reducedHeight"],
                conversion_metadata["fileSizeBytes"],
            )
            
            # Salva imagem para debug
            _save_debug_image(base64_image, image_format, piece_id, campaign_id)
            
            # Envia HTML + imagem para o Legal Service (análise visual + textual)
            content_for_compliance = {"html": raw, "image": data_url}
            
            # Guarda HTML original para validação de branding (paralela)
            html_for_branding = raw
            
        except Exception as e:
            err = str(e)
            logger.warning("HTML to image conversion error: %s", err)
            return {
                "retrieve_ok": False,
                "retrieve_error": f"Erro ao converter HTML para imagem: {err}",
                "requires_human_approval": True,
                "human_approval_reason": f"Exceção na conversão HTML->imagem: {err}",
            }
    else:
        content_for_compliance = {"html": raw}

    return {
        "retrieve_ok": True,
        "content_for_compliance": content_for_compliance,
        "html_for_branding": html_for_branding,
        "image_for_branding": image_for_branding,
        "conversion_metadata": conversion_metadata,
        "retrieved_content_hash": retrieved_content_hash,
    }


async def validate_specs_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    3) validate_specs: validação determinística de specs técnicos.

    Busca specs via MCP (campaigns-service) e valida dimensões de imagem,
    peso de arquivos e limites de caracteres. Fail-fast: se specs inválidos,
    bloqueia antes de gastar tokens no legal-service.

    Fallback: se MCP indisponível, usa channel_specs.yaml local.
    """
    _node_start = time.perf_counter()
    channel = (state.get("channel") or "").upper()
    content = state.get("content") or {}
    content_for_compliance = state.get("content_for_compliance") or {}
    conversion_metadata = state.get("conversion_metadata")

    # Determina o conteúdo real para validar specs
    if channel in ("SMS", "PUSH"):
        specs_content = content
    else:
        specs_content = content_for_compliance

    # Determina commercial_space (para APP)
    commercial_space = None
    if channel == "APP":
        commercial_space = (
            content.get("commercial_space")
            or content.get("commercialSpace")
        )

    # Busca specs via MCP (campaigns-service)
    remote_specs = None
    try:
        remote_specs = await fetch_channel_specs.ainvoke({
            "channel": channel,
            "commercial_space": commercial_space,
        })
        if remote_specs.get("error"):
            logger.warning("fetch_channel_specs returned error: %s — using local fallback", remote_specs["error"])
            remote_specs = None
        else:
            logger.info(
                "fetch_channel_specs: channel=%s, space=%s, specs_fields=%s",
                channel, commercial_space,
                list(remote_specs.get("specs", {}).keys()),
            )
    except Exception as e:
        logger.warning("fetch_channel_specs MCP failed: %s — using local fallback", e)

    specs_result = validate_piece_specs(
        channel=channel,
        content=specs_content,
        commercial_space=commercial_space,
        conversion_metadata=conversion_metadata,
        remote_specs=remote_specs,
    )

    specs_valid = specs_result.get("valid", True)
    specs_errors = specs_result.get("errors")
    specs_warnings = specs_result.get("warnings")

    logger.info(
        "validate_specs: channel=%s, valid=%s, errors=%d, warnings=%d, source=%s",
        channel,
        specs_valid,
        len(specs_errors) if specs_errors else 0,
        len(specs_warnings) if specs_warnings else 0,
        specs_result.get("details", {}).get("specs_source", "unknown"),
    )

    NODE_DURATION.labels(node="validate_specs", channel=channel).observe(time.perf_counter() - _node_start)
    SPECS_RESULT.labels(channel=channel, result="pass" if specs_valid else "fail").inc()

    return {
        "specs_ok": specs_valid,
        "specs_result": specs_result,
    }


async def validate_compliance_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    4) validate_compliance: chama legal-service via A2A.

    Roda em paralelo com specs e branding — sem guards.
    Depende apenas de content_for_compliance (preenchido por validate_channel ou retrieve_content).
    """
    _node_start = time.perf_counter()
    channel = (state.get("channel") or "").upper()
    content_for_compliance = state.get("content_for_compliance") or {}

    if not content_for_compliance:
        NODE_DURATION.labels(node="validate_compliance", channel=channel).observe(time.perf_counter() - _node_start)
        return {
            "compliance_ok": False,
            "compliance_error": "Nenhum conteúdo para validar.",
        }

    a2a_start = time.perf_counter()
    try:
        result = await validate_legal_compliance.ainvoke({
            "channel": channel,
            "content": content_for_compliance,
            "task": "VALIDATE_COMMUNICATION",
        })
        A2A_DURATION.labels(channel=channel).observe(time.perf_counter() - a2a_start)
        A2A_CALLS.labels(channel=channel, status="success").inc()
    except Exception as e:
        A2A_DURATION.labels(channel=channel).observe(time.perf_counter() - a2a_start)
        A2A_CALLS.labels(channel=channel, status="error").inc()
        err = str(e)
        logger.warning("validate_compliance A2A error: %s", err)
        NODE_DURATION.labels(node="validate_compliance", channel=channel).observe(time.perf_counter() - _node_start)
        return {
            "compliance_ok": False,
            "compliance_error": err,
        }

    decision = result.get("decision", "REPROVADO")
    requires_human = result.get("requires_human_review", True)
    summary = result.get("summary", "")
    sources = result.get("sources", [])

    NODE_DURATION.labels(node="validate_compliance", channel=channel).observe(time.perf_counter() - _node_start)

    return {
        "compliance_ok": True,
        "compliance_result": {
            "decision": decision,
            "requires_human_review": requires_human,
            "summary": summary,
            "sources": sources,
        },
    }


async def validate_branding_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    5) validate_branding: valida conformidade de marca via branding-service (MCP).
    
    Roda em paralelo com validate_specs (ambos determinísticos).
    
    - EMAIL: valida HTML (cores, tipografia, logo, layout, CTAs, footer, links)
    - APP: valida imagem (cores dominantes contra paleta aprovada)
    - SMS/PUSH: skip (sem conteúdo visual para validar)
    """
    _node_start = time.perf_counter()
    channel = (state.get("channel") or "").upper()
    html_for_branding = state.get("html_for_branding")
    image_for_branding = state.get("image_for_branding")
    
    if channel in ("SMS", "PUSH") or (not html_for_branding and not image_for_branding):
        logger.info("validate_branding: skipping (channel=%s, has_html=%s, has_image=%s)",
                     channel, bool(html_for_branding), bool(image_for_branding))
        return {
            "branding_ok": True,
            "branding_result": None,
            "branding_error": None,
        }
    
    try:
        if channel == "EMAIL" and html_for_branding:
            # Valida HTML de email (cores, fontes, logo, layout, CTAs, footer, links)
            result = await validate_brand_compliance.ainvoke({"html": html_for_branding})
        elif image_for_branding:
            # Valida imagem (cores dominantes contra paleta)
            result = await validate_image_brand_compliance.ainvoke({"image": image_for_branding})
        else:
            logger.info("validate_branding: no content to validate")
            return {
                "branding_ok": True,
                "branding_result": None,
                "branding_error": None,
            }
    except Exception as e:
        err = str(e)
        logger.warning("validate_branding MCP error (channel=%s): %s", channel, err)
        return {
            "branding_ok": False,
            "branding_error": err,
            "branding_result": {
                "compliant": False,
                "score": 0,
                "violations": [],
                "summary": {"critical": 0, "warning": 0, "info": 0, "total": 0},
                "error": err,
            },
        }
    
    compliant = result.get("compliant", False)
    score = result.get("score", 0)
    violations = result.get("violations", [])
    summary = result.get("summary", {})
    
    branding_result = {
        "compliant": compliant,
        "score": score,
        "violations": violations,
        "summary": summary,
        "validation_type": "html" if (channel == "EMAIL" and html_for_branding) else "image",
    }
    if "dominant_colors" in result:
        branding_result["dominant_colors"] = result["dominant_colors"]
    
    logger.info(
        "validate_branding: channel=%s, type=%s, compliant=%s, score=%d, violations=%d",
        channel, branding_result["validation_type"],
        compliant, score, summary.get("total", 0),
    )
    
    NODE_DURATION.labels(node="validate_branding", channel=channel).observe(time.perf_counter() - _node_start)
    BRANDING_RESULT.labels(channel=channel, compliant=str(compliant).lower()).inc()

    return {
        "branding_ok": True,
        "branding_result": branding_result,
    }


def issue_final_verdict_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    issue_final_verdict: agrega os resultados de specs, branding e compliance.

    Não usa LLM — apenas consolida os retornos dos 3 nós paralelos em um
    único payload com decisão final.

    Possíveis cenários de entrada (early-fail):
    - validate_channel falhou → specs/branding/compliance não executaram
    - retrieve_content falhou → specs/branding/compliance não executaram
    - Os 3 executaram (paralelo) → agrega tudo
    """
    validation_result = state.get("validation_result") or {}
    validation_valid = state.get("validation_valid", False)
    retrieve_ok = state.get("retrieve_ok", False)
    retrieve_error = state.get("retrieve_error")
    channel = (state.get("channel") or "").upper()

    specs_ok = state.get("specs_ok")              
    specs_result = state.get("specs_result")

    branding_ok = state.get("branding_ok")          
    branding_result = state.get("branding_result")
    branding_error = state.get("branding_error")

    compliance_ok = state.get("compliance_ok", False)
    compliance_result = state.get("compliance_result") or {}
    compliance_error = state.get("compliance_error")

    stages_completed: list[str] = []
    failure_stage: str | None = None

    if not validation_valid:
        failure_stage = "validate_channel"
        validation_msg = validation_result.get("message", "Formato ou canal inválido")
        return _build_verdict(
            decision="REPROVADO",
            summary=f"Formato: {validation_msg}",
            requires_human=True,
            human_reason=validation_msg,
            failure_stage=failure_stage,
            stages_completed=stages_completed,
            validation_result=validation_result,
        )

    stages_completed.append("validate_channel")

    if channel in ("EMAIL", "APP") and not retrieve_ok:
        failure_stage = "retrieve_content"
        err = retrieve_error or "Falha ao buscar conteúdo da peça"
        return _build_verdict(
            decision="REPROVADO",
            summary=f"Retrieve: {err}",
            requires_human=True,
            human_reason=err,
            failure_stage=failure_stage,
            stages_completed=stages_completed,
            validation_result=validation_result,
        )

    if channel in ("EMAIL", "APP"):
        stages_completed.append("retrieve_content")

    sources: list[dict] = []
    requires_human = False

    summary_lines: list[str] = []

    specs_passed = True
    specs_warnings: list[str] = []
    if specs_ok is not None:
        stages_completed.append("validate_specs")
    if specs_ok is False:
        specs_passed = False
        specs_errors = specs_result.get("errors", []) if specs_result else []
        detail = "; ".join(specs_errors[:3]) if specs_errors else "Specs técnicos inválidos"
        summary_lines.append(f"[Specs] {detail}")
    elif specs_result:
        specs_warnings = specs_result.get("warnings") or []
        if specs_warnings:
            summary_lines.append(f"[Specs] {len(specs_warnings)} aviso(s)")

    branding_passed = True
    branding_score = 100
    if branding_ok is not None or branding_result:
        stages_completed.append("validate_branding")
    if branding_result:
        branding_score = branding_result.get("score", 100)
        branding_compliant = branding_result.get("compliant", True)
        if not branding_compliant:
            branding_passed = False
            violations = branding_result.get("violations") or []
            violations_total = branding_result.get("summary", {}).get("total", 0)
            header = f"[Marca] {violations_total} violação(ões), score {branding_score}/100"
            if violations:
                details = "; ".join(
                    v.get("message", v.get("rule", "?")) for v in violations[:5]
                )
                summary_lines.append(f"{header}: {details}")
            else:
                summary_lines.append(header)
    if branding_error and not branding_result:
        summary_lines.append(f"[Marca] Erro — {branding_error[:120]}")

    legal_passed = True
    legal_decision = None
    legal_summary = ""
    if compliance_ok:
        stages_completed.append("validate_compliance")
        legal_decision = compliance_result.get("decision", "REPROVADO")
        legal_summary = compliance_result.get("summary", "")
        legal_sources = compliance_result.get("sources", [])
        sources.extend(legal_sources)
        requires_human = compliance_result.get("requires_human_review", False)

        if legal_decision != "APROVADO":
            legal_passed = False
            summary_lines.append(f"[Legal] {legal_summary}" if legal_summary else "[Legal] Reprovado")
        elif legal_summary:
            summary_lines.append(f"[Legal] {legal_summary}")
    elif compliance_error:
        legal_passed = False
        summary_lines.append(f"[Legal] Erro — {compliance_error[:200]}")
        requires_human = True

    all_passed = specs_passed and branding_passed and legal_passed and legal_decision == "APROVADO"
    final_decision = "APROVADO" if all_passed else "REPROVADO"

    if summary_lines:
        summary = "\n".join(summary_lines)
    elif final_decision == "APROVADO":
        summary = "Todas as validações passaram."
    else:
        summary = "Reprovado."

    return _build_verdict(
        decision=final_decision,
        summary=summary,
        requires_human=requires_human,
        human_reason=summary if requires_human else None,
        failure_stage=None,
        stages_completed=stages_completed,
        validation_result=validation_result,
        specs_result=specs_result,
        branding_result=branding_result,
        compliance_result=compliance_result if compliance_ok else None,
        compliance_error=compliance_error,
        sources=sources,
    )


def _build_verdict(
    *,
    decision: str,
    summary: str,
    requires_human: bool = False,
    human_reason: str | None = None,
    failure_stage: str | None,
    stages_completed: list[str],
    validation_result: dict | None = None,
    specs_result: dict | None = None,
    branding_result: dict | None = None,
    compliance_result: dict | None = None,
    compliance_error: str | None = None,
    sources: list | None = None,
) -> Dict[str, Any]:
    final_verdict = {
        "decision": decision,
        "requires_human_review": requires_human,
        "summary": summary,
        "sources": sources or [],
        "failure_stage": failure_stage,
        "stages_completed": stages_completed,
        "specs": specs_result,
        "legal": {
            "decision": compliance_result.get("decision"),
            "summary": compliance_result.get("summary"),
        } if compliance_result else None,
        "branding": branding_result,
    }

    orchestration_result = {
        "validation": validation_result,
        "specs": specs_result,
        "branding": branding_result,
        "compliance": compliance_result if compliance_result else {"error": compliance_error},
        "final_verdict": final_verdict,
        "requires_human_approval": requires_human,
        "human_approval_reason": human_reason,
        "failure_stage": failure_stage,
        "stages_completed": stages_completed,
    }

    return {
        "final_verdict": final_verdict,
        "orchestration_result": orchestration_result,
        "requires_human_approval": requires_human,
        "human_approval_reason": human_reason,
    }
