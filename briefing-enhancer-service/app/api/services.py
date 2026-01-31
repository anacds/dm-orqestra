import logging
import uuid
from sqlalchemy.orm import Session
from typing import Dict
from datetime import datetime, timezone
from app.api.schemas import EnhanceObjectiveRequest, EnhanceObjectiveResponse, UpdateInteractionDecisionRequest
from app.agent.graph import run_enhancement_graph
from app.models.ai_interaction import AIInteraction
from langsmith import traceable

logger = logging.getLogger(__name__)

class AIService:

    @staticmethod
    def _generate_thread_id(session_id: str | None, campaign_id: str | None) -> str:
        """
        Generate thread_id based on fixed priority: session_id > campaign_id > new UUID.
        
        Strategy (FIXED - frontend doesn't choose):
        - Durante criação de campanha: frontend SEMPRE envia session_id -> usa session_id
        - Editando campanha existente: frontend NÃO envia session_id -> usa campaign_id
        - Fallback: gera novo UUID se nenhum estiver disponível (não deveria acontecer)
        
        O frontend não escolhe - é o backend que decide baseado no que recebe:
        - Se recebe session_id -> usa session_id (contexto da sessão de criação)
        - Se NÃO recebe session_id mas recebe campaign_id -> usa campaign_id (contexto da campanha existente)
        
        Args:
            session_id: Session ID do frontend (apenas durante criação de campanha)
            campaign_id: Campaign ID (após criação ou ao editar campanha existente)
        
        Returns:
            Thread ID string para checkpointing
        """
        if session_id:
            # Prioridade 1: Sempre usa session_id se existir (contexto da sessão de criação)
            thread_id = f"session_{session_id}"
            logger.debug(f"Using thread_id from session_id: {thread_id}")
            return thread_id
        elif campaign_id:
            # Prioridade 2: Usa campaign_id se não houver session_id (editando campanha existente)
            thread_id = f"campaign_{campaign_id}"
            logger.debug(f"Using thread_id from campaign_id: {thread_id}")
            return thread_id
        else:
            # Prioridade 3: Gera novo UUID (fallback, não deveria acontecer no fluxo normal)
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
        
        # Low-cost cache using previous AI interactions in Postgres
        cache_query = db.query(AIInteraction).filter(
            AIInteraction.user_id == user_id,
            AIInteraction.field_name == request_data.field_name,
            AIInteraction.input_text == request_data.text,
        )

        # Keep cache scoped to the same campaign when possível
        if request_data.campaign_id:
            cache_query = cache_query.filter(AIInteraction.campaign_id == request_data.campaign_id)

        # If there is a session_id (creating campaign), prefer interactions from same session
        if request_data.session_id:
            cache_query = cache_query.filter(AIInteraction.session_id == request_data.session_id)

        # Do not reuse outputs explicitly rejected by the user
        cache_query = cache_query.filter(AIInteraction.user_decision != "rejected")

        cached_interaction = cache_query.order_by(AIInteraction.created_at.desc()).first()

        if cached_interaction:
            logger.info(
                f"Returning cached enhancement for user {user_id}, field '{request_data.field_name}', "
                f"campaign_id={request_data.campaign_id}, session_id={request_data.session_id} "
                f"(interaction_id={cached_interaction.id})"
            )
            return EnhanceObjectiveResponse(
                enhanced_text=cached_interaction.output_text,
                explanation=cached_interaction.explanation,
                interaction_id=cached_interaction.id,
            )
        
        # Generate thread_id for checkpointing (backend derives internally, frontend doesn't know about it)
        thread_id = AIService._generate_thread_id(
            session_id=request_data.session_id,
            campaign_id=request_data.campaign_id
        )
        
        logger.info(f"Using thread_id for checkpointing: {thread_id}")
        
        # Run graph with checkpointing enabled (uses thread_id internally)
        try:
            logger.debug(f"Calling run_enhancement_graph with thread_id: {thread_id}")
            result = await run_enhancement_graph(
                field_name=request_data.field_name,
                text=request_data.text,
                db=db,
                thread_id=thread_id,
                use_checkpointing=True,
                campaign_name=request_data.campaign_name
            )
            logger.debug(f"run_enhancement_graph completed successfully")
        except Exception as e:
            logger.error(
                f"EXCEPTION in run_enhancement_graph for thread_id {thread_id}",
                exc_info=True
            )
            raise
        
        # audit
        interaction = AIInteraction(
            user_id=user_id,
            campaign_id=request_data.campaign_id,
            field_name=request_data.field_name,
            input_text=request_data.text,
            output_text=result["enhanced_text"],
            explanation=result["explanation"],
            session_id=request_data.session_id
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        
        logger.info(f"Interaction logged with ID: {interaction.id}")
        
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
            AIInteraction.user_id == user_id  # Ensure user can only update their own interactions
        ).first()
        
        if not interaction:
            logger.warning(f"Interaction {interaction_id} not found or access denied for user {user_id}")
            raise ValueError("Interaction not found or access denied")
        
        interaction.user_decision = request_data.decision
        interaction.decision_at = datetime.now(timezone.utc)
        db.commit()
        
        logger.info(f"Successfully updated interaction {interaction_id} decision to '{request_data.decision}'")

