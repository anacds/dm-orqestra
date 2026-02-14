import re
import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.api.schemas import (
    AppContent,
    EmailContent,
    PUSHContent,
    SMSContent,
    ValidationInput,
    ValidationOutput,
)
from app.agent.graph import LegalAgent
from app.core.config import settings
from app.core.models_config import load_models_config
from app.core.database import get_db
from app.models.validation_audit import LegalValidationAudit

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = APIRouter()


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text

_agent: Optional[LegalAgent] = None


def get_agent() -> LegalAgent:
    global _agent
    if _agent is None:
        maritaca_api_key = (os.getenv("MARITACA_API_KEY") or "").strip()
        openai_api_key = (settings.OPENAI_API_KEY or "").strip()

        if not maritaca_api_key and not openai_api_key:
            raise HTTPException(
                status_code=500,
                detail="Nenhuma MARITACA_API_KEY ou OPENAI_API_KEY configurada",
            )

        config = load_models_config()
        llm_config = config.get("models", {}).get("llm", {})
        defaults = llm_config.get("defaults", {})
        embeddings_config = config.get("models", {}).get("embeddings", {})
        
        _agent = LegalAgent(
            weaviate_url=settings.WEAVIATE_URL,
            embedding_model=embeddings_config.get("model", "text-embedding-3-small"),
            temperature=float(defaults.get("temperature", llm_config.get("temperature", 0.0))),
            redis_url=settings.REDIS_URL,
            cache_enabled=settings.CACHE_ENABLED,
            cache_ttl=settings.CACHE_TTL,
        )
        logger.info("Agent initialized")
    return _agent


@router.get("/health")
async def health():
    llm = load_models_config().get("models", {}).get("llm", {})
    channels = llm.get("channels", {})
    llm_by_channel = {
        ch: {"provider": c.get("provider"), "model": c.get("model")}
        for ch, c in (channels or {}).items()
    }
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "weaviate_url": settings.WEAVIATE_URL,
        "llm_by_channel": llm_by_channel,
    }


@router.post("/validate", response_model=ValidationOutput)
async def validate_communication(
    request: Request,
    input_data: ValidationInput,
    db: Session = Depends(get_db)
):
    try:
        agent = get_agent()
        
        logger.info(f"Validating communication: channel={input_data.channel}, task={input_data.task}")

        content_title = None
        content_body = None
        content_image = None

        if isinstance(input_data.content, PUSHContent):
            content_title = input_data.content.title
            content_body = input_data.content.body
        elif isinstance(input_data.content, SMSContent):
            content_body = input_data.content.body
        elif isinstance(input_data.content, EmailContent):
            if input_data.content.html:
                content_body = _strip_html(input_data.content.html)
            if input_data.content.image:
                content_image = input_data.content.image
            logger.info("EMAIL: html=%s, image=%s", 
                       "yes" if input_data.content.html else "no",
                       "yes" if input_data.content.image else "no")
        elif isinstance(input_data.content, AppContent):
            content_image = input_data.content.image
        else:
            content_title = getattr(input_data.content, "title", None)
            content_body = getattr(input_data.content, "body", None) or getattr(input_data.content, "content", "")
            content_image = getattr(input_data.content, "image", None)

        if content_title and content_body:
            content_str = f"{content_title}\n\n{content_body}"
        elif content_body:
            content_str = content_body
        else:
            content_str = ""
        if content_image and not content_body:
            content_str = f"[{input_data.channel} 1 imagem]"
        elif content_image and content_body:
            content_str = f"{content_body}\n[+ 1 imagem anexa]"
        
        result = agent.invoke(
            task=input_data.task,
            channel=input_data.channel,
            content=content_str or ("[APP 1 imagem]" if content_image else ""),
            content_title=content_title,
            content_body=content_body,
            content_image=content_image,
        )
        
        internal_metadata = result.pop("_internal", {})
        retrieved_chunks = internal_metadata.get("retrieved_chunks", [])
        search_metadata = internal_metadata.get("search_metadata")
        
        if not result.get("sources") and not retrieved_chunks:
            raise HTTPException(
                status_code=503,
                detail="Nenhum documento encontrado no Weaviate. Por favor, execute a ingestão de documentos primeiro."
            )
        
        try:
            filtered_result = {
                "decision": result.get("decision"),
                "requires_human_review": result.get("requires_human_review"),
                "summary": result.get("summary"),
                "sources": result.get("sources", []),
            }
            output = ValidationOutput(**filtered_result)
            
            content_hash = LegalValidationAudit.generate_content_hash(content_str)
            search_query = None
            if search_metadata:
                search_query = search_metadata.get("query")
            
            llm_model = None
            if input_data.channel and getattr(agent, "channel_to_model", None):
                if input_data.channel == "EMAIL" and content_image:
                    llm_model = agent.channel_to_model.get("APP")
                else:
                    llm_model = agent.channel_to_model.get(input_data.channel)
            if llm_model is None:
                llm_model = next(
                    iter(getattr(agent, "channel_to_model", {}).values()),
                    "sabiazinho-4",
                )
            audit = LegalValidationAudit(
                task=input_data.task,
                channel=input_data.channel,
                content_hash=content_hash,
                content_preview=content_str[:500] if len(content_str) > 500 else content_str,
                decision=output.decision,
                requires_human_review=output.requires_human_review,
                summary=output.summary,
                sources=output.sources,
                num_chunks_retrieved=internal_metadata.get("num_chunks_retrieved"),
                llm_model=llm_model,
                search_query=search_query
            )
            db.add(audit)
            db.commit()
            db.refresh(audit)
            
            logger.info(f"Validation audit logged with ID: {audit.id}")
            
            return output
        except ValidationError as e:
            logger.error(f"Validation error in output: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao validar output: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "could not find class" in error_msg.lower() or "not found in weaviate" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="Documentos não indexados. Execute a ingestão de documentos primeiro."
            )
        logger.error(f"Error validating communication: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar validação: {str(e)}"
        )

