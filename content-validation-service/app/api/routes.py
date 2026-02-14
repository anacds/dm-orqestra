import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agent import ContentValidationAgent
from app.api.schemas import AnalyzePieceRequest, AnalyzePieceResponse
from app.core.auth_client import get_current_user
from app.core.cache import ValidationCacheManager
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import require_ai_validation_access
from app.models.piece_validation_cache import PieceValidationAudit

router = APIRouter()
router_ai = APIRouter()
logger = logging.getLogger(__name__)

_agent: Optional[ContentValidationAgent] = None
_cache: Optional[ValidationCacheManager] = None


def get_agent() -> ContentValidationAgent:
    global _agent
    if _agent is None:
        _agent = ContentValidationAgent()
        logger.info("ContentValidationAgent initialized")
    return _agent


def get_cache() -> ValidationCacheManager:
    global _cache
    if _cache is None:
        _cache = ValidationCacheManager(
            redis_url=settings.REDIS_URL,
            enabled=settings.CACHE_ENABLED,
            ttl=settings.CACHE_TTL,
        )
    return _cache


def _response_to_dict(resp: AnalyzePieceResponse) -> dict[str, Any]:
    return {
        "validation_result": resp.validation_result,
        "specs_result": resp.specs_result,
        "orchestration_result": resp.orchestration_result,
        "compliance_result": resp.compliance_result,
        "branding_result": resp.branding_result,
        "requires_human_approval": resp.requires_human_approval,
        "human_approval_reason": resp.human_approval_reason,
        "failure_stage": resp.failure_stage,
        "stages_completed": resp.stages_completed,
        "final_verdict": resp.final_verdict,
    }


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "legal_service_url": settings.LEGAL_SERVICE_URL,
        "campaigns_mcp_url": settings.CAMPAIGNS_MCP_URL,
        "a2a": "GET /a2a/.well-known/agent-card.json, POST /a2a/v1/message:send",
    }


@router_ai.post("/ai/analyze-piece", response_model=AnalyzePieceResponse)
async def analyze_piece(
    body: AnalyzePieceRequest,
    agent: ContentValidationAgent = Depends(get_agent),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Valida peça criativa com cache transparente.

    SMS/PUSH: hash calculável a partir do conteúdo inline → cache check antes
    do agente. EMAIL/APP: hash depende do conteúdo real (fetch via MCP) →
    cache check só é possível após retrieve, feito dentro do agente.
    """
    require_ai_validation_access(current_user)
    cache = get_cache()

    # ── Resolve campaign_id ───────────────────────────────────────────
    cid = body.campaign_id or (
        body.content.get("campaign_id") if isinstance(body.content, dict) else None
    )
    cid = str(cid) if cid else None
    content_dict = body.content if isinstance(body.content, dict) else {}

    # ── Cache check (transparente para SMS/PUSH) ─────────────────────
    pre_hash: str | None = None
    if cid and body.channel in ("SMS", "PUSH"):
        pre_hash = ValidationCacheManager.compute_content_hash(
            channel=body.channel,
            content=content_dict,
        )
        if pre_hash:
            cached = cache.get(cid, body.channel, pre_hash)
            if cached:
                logger.info(
                    "Cache HIT (transparente) campaign_id=%s channel=%s",
                    cid, body.channel,
                )
                return AnalyzePieceResponse(**cached)

    # ── Executar agente ───────────────────────────────────────────────
    try:
        result = await agent.ainvoke(
            task=body.task,
            channel=body.channel,
            content=body.content,
        )
        final_verdict = result.get("final_verdict") or {}
        resp = AnalyzePieceResponse(
            validation_result=result.get("validation_result") or {},
            specs_result=result.get("specs_result"),
            orchestration_result=result.get("orchestration_result"),
            compliance_result=result.get("compliance_result"),
            branding_result=result.get("branding_result"),
            requires_human_approval=result.get("requires_human_approval", False),
            human_approval_reason=result.get("human_approval_reason"),
            failure_stage=final_verdict.get("failure_stage"),
            stages_completed=final_verdict.get("stages_completed"),
            final_verdict=final_verdict if final_verdict else None,
        )

        # ── Persistir cache + auditoria ──────────────────────────────
        if cid and body.channel in ("SMS", "PUSH", "EMAIL", "APP"):
            content_hash = pre_hash or ValidationCacheManager.compute_content_hash(
                channel=body.channel,
                content=content_dict,
                retrieved_content_hash=result.get("retrieved_content_hash"),
            )

            if content_hash:
                payload = _response_to_dict(resp)

                cache.set(cid, body.channel, content_hash, payload)

                try:
                    db.add(PieceValidationAudit(
                        campaign_id=cid,
                        channel=body.channel,
                        content_hash=content_hash,
                        response_json=payload,
                    ))
                    db.commit()
                    logger.info(
                        "Audit saved campaign_id=%s channel=%s hash=%s",
                        cid, body.channel, content_hash[:16],
                    )
                except Exception as e:
                    db.rollback()
                    logger.error("Erro ao salvar audit: %s", e)

        return resp
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("analyze_piece error: %s", e)
        raise HTTPException(500, f"Error analyzing piece: {e}") from e


