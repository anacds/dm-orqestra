import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agent import ContentValidationAgent
from app.api.schemas import AnalyzePieceRequest, AnalyzePieceResponse
from app.core.auth_client import get_current_user
from app.core.config import settings
from app.core.permissions import require_creative_analyst
from app.core.database import get_db
from app.models.piece_validation_cache import (
    PieceValidationCache,
    content_hash_app,
    content_hash_email,
    content_hash_push,
    content_hash_sms,
)

router = APIRouter()
router_ai = APIRouter()
logger = logging.getLogger(__name__)

_agent: Optional[ContentValidationAgent] = None


def get_agent() -> ContentValidationAgent:
    global _agent
    if _agent is None:
        _agent = ContentValidationAgent()
        logger.info("ContentValidationAgent initialized")
    return _agent


def _response_to_dict(resp: AnalyzePieceResponse) -> dict[str, Any]:
    return {
        "validation_result": resp.validation_result,
        "orchestration_result": resp.orchestration_result,
        "compliance_result": resp.compliance_result,
        "branding_result": resp.branding_result,
        "requires_human_approval": resp.requires_human_approval,
        "human_approval_reason": resp.human_approval_reason,
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
    """Valida canal, retrieve (MCP), validate_compliance (A2A), issue_final_verdict. Persiste parecer para SMS/PUSH se campaign_id enviado."""
    require_creative_analyst(current_user)
    try:
        result = await agent.ainvoke(
            task=body.task,
            channel=body.channel,
            content=body.content,
        )
        resp = AnalyzePieceResponse(
            validation_result=result.get("validation_result") or {},
            orchestration_result=result.get("orchestration_result"),
            compliance_result=result.get("compliance_result"),
            branding_result=result.get("branding_result"),
            requires_human_approval=result.get("requires_human_approval", False),
            human_approval_reason=result.get("human_approval_reason"),
            final_verdict=result.get("final_verdict"),
        )
        cid = body.campaign_id or (body.content.get("campaign_id") if isinstance(body.content, dict) else None)
        cid = str(cid) if cid else None
        ch = body.content if isinstance(body.content, dict) else {}

        if cid and body.channel in ("SMS", "PUSH", "EMAIL", "APP"):
            if body.channel == "SMS":
                h = content_hash_sms(ch.get("body") if isinstance(ch.get("body"), str) else None)
            elif body.channel == "PUSH":
                h = content_hash_push(
                    ch.get("title") if isinstance(ch.get("title"), str) else None,
                    ch.get("body") if isinstance(ch.get("body"), str) else None,
                )
            elif body.channel == "EMAIL":
                pid = ch.get("piece_id") or ch.get("pieceId")
                if pid:
                    h = content_hash_email(str(pid))
                else:
                    h = None
            else:
                pid = ch.get("piece_id") or ch.get("pieceId")
                space = ch.get("commercial_space") or ch.get("commercialSpace")
                if pid and space:
                    h = content_hash_app(str(pid), str(space))
                else:
                    h = None

            if h:
                row = db.query(PieceValidationCache).filter(
                    PieceValidationCache.campaign_id == cid,
                    PieceValidationCache.channel == body.channel,
                    PieceValidationCache.content_hash == h,
                ).first()
                payload = _response_to_dict(resp)
                if row:
                    row.response_json = payload
                    db.commit()
                else:
                    db.add(PieceValidationCache(
                        campaign_id=cid,
                        channel=body.channel,
                        content_hash=h,
                        response_json=payload,
                    ))
                    db.commit()
                logger.info("Cached analyze-piece campaign_id=%s channel=%s content_hash=%s", cid, body.channel, h[:16])
        return resp
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("analyze_piece error: %s", e)
        raise HTTPException(500, f"Error analyzing piece: {e}") from e


@router_ai.get("/ai/analyze-piece/{campaign_id}/{channel}", response_model=AnalyzePieceResponse)
async def get_analyze_piece(
    campaign_id: str,
    channel: str,
    content_hash: Optional[str] = Query(None, description="Hash do conteúdo (SMS ou Push). Obrigatório para SMS/PUSH."),
    piece_id: Optional[str] = Query(None, description="ID da peça (E-mail ou App). Obrigatório para EMAIL/APP."),
    commercial_space: Optional[str] = Query(None, description="Espaço comercial. Obrigatório para APP."),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Retorna parecer persistido para SMS/PUSH/EMAIL/APP. Usado ao recarregar a página de detalhes da campanha."""
    require_creative_analyst(current_user)
    ch = channel.upper().replace("-", "").replace(" ", "")
    if ch not in ("SMS", "PUSH", "EMAIL", "APP"):
        raise HTTPException(400, "GET suporta apenas canal SMS, PUSH, EMAIL ou APP.")

    if ch in ("SMS", "PUSH"):
        if not content_hash:
            raise HTTPException(400, "Para SMS/PUSH, informe content_hash.")
        h = content_hash
    elif ch == "EMAIL":
        if not piece_id:
            raise HTTPException(400, "Para EMAIL, informe piece_id.")
        h = content_hash_email(piece_id)
    else:
        if not piece_id or not commercial_space:
            raise HTTPException(400, "Para APP, informe piece_id e commercial_space.")
        h = content_hash_app(piece_id, commercial_space)

    row = db.query(PieceValidationCache).filter(
        PieceValidationCache.campaign_id == campaign_id,
        PieceValidationCache.channel == ch,
        PieceValidationCache.content_hash == h,
    ).first()
    if not row:
        raise HTTPException(404, "Parecer não encontrado para este conteúdo.")
    return AnalyzePieceResponse(**row.response_json)


@router_ai.post("/ai/generate-text")
async def generate_text(
    current_user: Dict = Depends(get_current_user),
):
    require_creative_analyst(current_user)
    raise HTTPException(501, "Not implemented. Use analyze-piece or legal-service.")
