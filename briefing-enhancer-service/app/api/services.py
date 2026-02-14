import logging
import uuid
from sqlalchemy.orm import Session
from typing import Dict, Optional
from datetime import datetime, timezone
from app.api.schemas import EnhanceObjectiveRequest, EnhanceObjectiveResponse, UpdateInteractionDecisionRequest
from app.agent.graph import run_enhancement_graph
from app.core.cache import EnhancementCacheManager
from app.core.config import settings
from app.models.ai_interaction import AIInteraction
from langsmith import traceable

logger = logging.getLogger(__name__)

_cache: Optional[EnhancementCacheManager] = None


def get_cache() -> EnhancementCacheManager:
    global _cache
    if _cache is None:
        _cache = EnhancementCacheManager(
            redis_url=settings.REDIS_URL,
            enabled=settings.CACHE_ENABLED,
            ttl=settings.CACHE_TTL,
        )
    return _cache


class AIService:

    @staticmethod
    def _generate_thread_id(session_id: str | None, campaign_id: str | None) -> str:
        if session_id:
            thread_id = f"session_{session_id}"
            logger.debug(f"Using thread_id from session_id: {thread_id}")
            return thread_id
        elif campaign_id:
            thread_id = f"campaign_{campaign_id}"
            logger.debug(f"Using thread_id from campaign_id: {thread_id}")
            return thread_id
        else:
            thread_id = f"new_{str(uuid.uuid4())}"
            logger.warning(f"No session_id or campaign_id provided, generating new thread_id: {thread_id}")
            return thread_id

    @traceable
    @staticmethod
    async def enhance_objective(
        request_data: EnhanceObjectiveRequest,
        db: Session,
        user_id: str
    ) -> EnhanceObjectiveResponse:
        logger.info(
            f"Enhancing text for user {user_id}, field '{request_data.field_name}', "
            f"campaign_id={request_data.campaign_id}, session_id={request_data.session_id} "
            f"(text length: {len(request_data.text)} chars)"
        )

        cache = get_cache()

        cached = cache.get(
            user_id=user_id,
            field_name=request_data.field_name,
            input_text=request_data.text,
            campaign_id=request_data.campaign_id,
            session_id=request_data.session_id,
        )
        if cached:
            logger.info(
                f"Returning cached enhancement for user {user_id}, "
                f"field '{request_data.field_name}'"
            )
            return EnhanceObjectiveResponse(
                enhanced_text=cached["enhanced_text"],
                explanation=cached["explanation"],
                interaction_id=cached.get("interaction_id", ""),
            )

        thread_id = AIService._generate_thread_id(
            session_id=request_data.session_id,
            campaign_id=request_data.campaign_id
        )
        logger.info(f"Using thread_id for checkpointing: {thread_id}")

        try:
            result = await run_enhancement_graph(
                field_name=request_data.field_name,
                text=request_data.text,
                db=db,
                thread_id=thread_id,
                use_checkpointing=True,
                campaign_name=request_data.campaign_name
            )
        except Exception as e:
            logger.error(
                f"EXCEPTION in run_enhancement_graph for thread_id {thread_id}",
                exc_info=True
            )
            raise

        interaction = AIInteraction(
            user_id=user_id,
            campaign_id=request_data.campaign_id,
            field_name=request_data.field_name,
            input_text=request_data.text,
            output_text=result["enhanced_text"],
            explanation=result["explanation"],
            llm_model=result.get("llm_model"),
            session_id=request_data.session_id,
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        logger.info(f"Audit logged with ID: {interaction.id}")

        result_dict = {
            "enhanced_text": result["enhanced_text"],
            "explanation": result["explanation"],
            "interaction_id": interaction.id,
        }
        cache.set(
            user_id=user_id,
            field_name=request_data.field_name,
            input_text=request_data.text,
            result=result_dict,
            campaign_id=request_data.campaign_id,
            session_id=request_data.session_id,
        )

        return EnhanceObjectiveResponse(
            enhanced_text=result["enhanced_text"],
            explanation=result["explanation"],
            interaction_id=interaction.id
        )

    @staticmethod
    async def update_interaction_decision(
        interaction_id: str,
        request_data: UpdateInteractionDecisionRequest,
        db: Session,
        user_id: str
    ) -> None:
        logger.info(f"Updating interaction {interaction_id} decision to '{request_data.decision}' for user {user_id}")

        interaction = db.query(AIInteraction).filter(
            AIInteraction.id == interaction_id,
            AIInteraction.user_id == user_id
        ).first()

        if not interaction:
            logger.warning(f"Interaction {interaction_id} not found or access denied for user {user_id}")
            raise ValueError("Interaction not found or access denied")

        interaction.user_decision = request_data.decision
        interaction.decision_at = datetime.now(timezone.utc)
        db.commit()

        if request_data.decision == "rejected":
            cache = get_cache()
            cache.invalidate(
                user_id=user_id,
                field_name=interaction.field_name,
                input_text=interaction.input_text,
                campaign_id=interaction.campaign_id,
                session_id=interaction.session_id,
            )

        logger.info(f"Successfully updated interaction {interaction_id} decision to '{request_data.decision}'")

