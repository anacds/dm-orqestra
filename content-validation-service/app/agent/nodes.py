from __future__ import annotations

import base64
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict

from app.agent.state import ValidationGraphState
from app.agent.tools import retrieve_piece_content, validate_legal_compliance, convert_html_to_image
from app.agent.validate_piece import validate_piece_format_and_size

logger = logging.getLogger(__name__)

_DATA_URL_IMAGE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=]+$")

# Pasta para salvar imagens de debug (montada como volume Docker)
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
    1) validate_channel:
    - SMS/PUSH: valida formato obrigatório; se OK -> validate_compliance_node.
    - EMAIL/APP: vai para o retrieve_content_node.
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
    2) retrieve_content: chama campaigns-mcp-server (MCP).
    Sucesso -> validate_compliance. Erro -> peça necessita aprovação humana.
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
    elif channel == "EMAIL":
        # --- CÓDIGO LEGADO: enviava HTML direto para o Legal Service ---
        # content_for_compliance = {"html": raw}
        # --- FIM CÓDIGO LEGADO ---
        
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
            
            logger.info(
                "EMAIL HTML converted to image: %dx%d, %d bytes",
                conversion_result.get("reducedWidth", 0),
                conversion_result.get("reducedHeight", 0),
                conversion_result.get("fileSizeBytes", 0),
            )
            
            # Salva imagem para debug
            _save_debug_image(base64_image, image_format, piece_id, campaign_id)
            
            # Envia HTML + imagem para o Legal Service (análise visual + textual)
            content_for_compliance = {"html": raw, "image": data_url}
            
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
    }


async def validate_compliance_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    3) validate_compliance: chama legal-service via A2A.
    """
    channel = (state.get("channel") or "").upper()
    content_for_compliance = state.get("content_for_compliance") or {}

    if not content_for_compliance:
        return {
            "compliance_ok": False,
            "compliance_error": "Nenhum conteúdo para validar.",
            "requires_human_approval": True,
            "human_approval_reason": "content_for_compliance vazio.",
        }

    try:
        result = await validate_legal_compliance.ainvoke({
            "channel": channel,
            "content": content_for_compliance,
            "task": "VALIDATE_COMMUNICATION",
        })
    except Exception as e:
        err = str(e)
        logger.warning("validate_compliance A2A error: %s", err)
        return {
            "compliance_ok": False,
            "compliance_error": err,
            "requires_human_approval": True,
            "human_approval_reason": f"Erro ao validar via Legal Service: {err}",
        }

    decision = result.get("decision", "REPROVADO")
    requires_human = result.get("requires_human_review", True)
    summary = result.get("summary", "")
    sources = result.get("sources", [])

    return {
        "compliance_ok": True,
        "compliance_result": {
            "decision": decision,
            "requires_human_review": requires_human,
            "summary": summary,
            "sources": sources,
        },
        "requires_human_approval": requires_human,
        "human_approval_reason": summary if requires_human else None,
    }


def issue_final_verdict_node(state: ValidationGraphState) -> Dict[str, Any]:
    """
    4) issue_final_verdict: consolida resultado final.
    """
    compliance_result = state.get("compliance_result") or {}
    validation_result = state.get("validation_result") or {}
    requires_human = state.get("requires_human_approval", False)
    human_reason = state.get("human_approval_reason")

    decision = compliance_result.get("decision", "REPROVADO")
    summary = compliance_result.get("summary", "")
    sources = compliance_result.get("sources", [])

    final_verdict = {
        "decision": decision,
        "requires_human_review": requires_human,
        "summary": summary,
        "sources": sources,
    }

    orchestration_result = {
        "validation": validation_result,
        "compliance": compliance_result,
        "final_verdict": final_verdict,
        "requires_human_approval": requires_human,
        "human_approval_reason": human_reason,
    }

    return {
        "final_verdict": final_verdict,
        "orchestration_result": orchestration_result,
    }
