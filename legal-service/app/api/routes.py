from fastapi import APIRouter, HTTPException, status, Request, Depends
from pydantic import ValidationError
import logging
from typing import Optional
from sqlalchemy.orm import Session
import os

from app.api.schemas import ValidationInput, ValidationOutput
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

_agent: Optional[LegalAgent] = None


def get_agent() -> LegalAgent:
    """Get or create LegalAgent instance."""
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
        embeddings_config = config.get("models", {}).get("embeddings", {})
        
        _agent = LegalAgent(
            weaviate_url=settings.WEAVIATE_URL,
            embedding_model=embeddings_config.get("model", "text-embedding-3-small"),
            temperature=float(llm_config.get("temperature", 0.0)),
            redis_url=settings.REDIS_URL,
            cache_enabled=settings.CACHE_ENABLED,
            cache_ttl=settings.CACHE_TTL,
        )
        logger.info("Agent initialized")
    return _agent


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "weaviate_url": settings.WEAVIATE_URL,
        "llm_model": load_models_config()
        .get("models", {})
        .get("llm", {})
        .get("name", "sabiazinho-4"),
    }


@router.post("/validate", response_model=ValidationOutput)
async def validate_communication(
    request: Request,
    input_data: ValidationInput,
    db: Session = Depends(get_db)
):
    """Validate communication content against legal guidelines."""
    try:
        agent = get_agent()
        
        logger.info(f"Validating communication: channel={input_data.channel}, task={input_data.task}")
        
        # Extrai title e body do content baseado no tipo
        content_title = None
        content_body = None
        
        # Novo formato: Pydantic model (PUSHContent ou SMSContent)
        from app.api.schemas import PUSHContent, SMSContent
        if isinstance(input_data.content, PUSHContent):
            content_title = input_data.content.title
            content_body = input_data.content.body
        elif isinstance(input_data.content, SMSContent):
            content_body = input_data.content.body
        else:
            # Fallback: se vier como dict (não deveria acontecer com validação Pydantic)
            content_title = getattr(input_data.content, "title", None)
            content_body = getattr(input_data.content, "body", None) or getattr(input_data.content, "content", "")
        
        # Para backward compatibility, mantém content como string concatenada
        if content_title and content_body:
            content_str = f"{content_title}\n\n{content_body}"
        else:
            content_str = content_body or ""
        
        result = agent.invoke(
            task=input_data.task,
            channel=input_data.channel,
            content=content_str,  # Mantido para backward compatibility
            content_title=content_title,
            content_body=content_body,
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
                "severity": result.get("severity"),
                "requires_human_review": result.get("requires_human_review"),
                "summary": result.get("summary"),
                "sources": result.get("sources", []),
            }
            output = ValidationOutput(**filtered_result)
            
            # Usa content_str (string) para gerar hash, não o objeto Pydantic
            content_hash = LegalValidationAudit.generate_content_hash(content_str)
            search_query = None
            if search_metadata:
                search_query = search_metadata.get("query")
            
            audit = LegalValidationAudit(
                task=input_data.task,
                channel=input_data.channel,
                content_hash=content_hash,
                content_preview=content_str[:500] if len(content_str) > 500 else content_str,
                decision=output.decision,
                severity=output.severity,
                requires_human_review=output.requires_human_review,
                summary=output.summary,
                sources=output.sources,
                num_chunks_retrieved=internal_metadata.get("num_chunks_retrieved"),
                llm_model=getattr(agent, "model_name", None)
                or load_models_config().get("models", {}).get("llm", {}).get("name", "sabiazinho-4"),
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

