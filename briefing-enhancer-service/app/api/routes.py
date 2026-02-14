from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session
from typing import Dict
from app.api.schemas import EnhanceObjectiveRequest, EnhanceObjectiveResponse, UpdateInteractionDecisionRequest
from app.api.services import AIService
from app.core.database import get_db
from app.core.auth_client import get_current_user
from app.core.permissions import require_business_analyst
from langsmith import traceable

router = APIRouter()

@traceable
@router.post(
    "/enhance-objective",
    response_model=EnhanceObjectiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Enhance campaign briefing text using AI",
    description="Enhance text for campaign briefing fields using AI-powered analysis and improvement.",
    responses={
        200: {
            "description": "Text successfully enhanced",
            "content": {
                "application/json": {
                    "example": {
                        "enhancedText": "Aumentar as vendas do produto X em 15% no trimestre Q2 de 2024, focando em novos clientes na região Sudeste.",
                        "explanation": "O texto foi aprimorado adicionando métricas específicas (15%), prazo definido (Q2 2024), segmento de clientes (novos clientes) e região geográfica (Sudeste), tornando o objetivo mensurável e acionável.",
                        "interactionId": "550e8400-e29b-41d4-a716-446655440000"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request (for example: empty text, invalid field name)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "The text cannot be empty"
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Invalid or missing authentication token"
        },
        500: {
            "description": "Internal server error during text enhancement",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error enhancing text: API error"
                    }
                }
            }
        }
    },
    tags=["ai"]
)
async def enhance_objective(
    request: Request,
    request_data: EnhanceObjectiveRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):

    require_business_analyst(current_user)
    try:
        return await AIService.enhance_objective(request_data, db, current_user["id"])
    except ValueError as e:
        # Validation errors (e.g., text length)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in enhance_objective endpoint: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enhancing text: {str(e)}"
        )

@router.patch(
    "/ai-interactions/{interaction_id}/decision",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update user decision for an AI interaction",
    description="Update the user's decision (approved/rejected) for a previously generated AI enhancement.",
    responses={
        204: {
            "description": "Decision successfully updated"
        },
        400: {
            "description": "Invalid request (for example: invalid decision value, interaction not found)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Decision must be 'approved' or 'rejected'"
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Invalid or missing authentication token"
        },
        403: {
            "description": "Forbidden - User cannot update this interaction (not the owner)"
        },
        404: {
            "description": "Interaction not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Interaction not found or access denied"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error updating interaction decision: Database error"
                    }
                }
            }
        }
    },
    tags=["interactions"]
)
async def update_interaction_decision(
    request: Request,
    interaction_id: str,
    request_data: UpdateInteractionDecisionRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):

    require_business_analyst(current_user)
    try:
        await AIService.update_interaction_decision(
            interaction_id=interaction_id,
            request_data=request_data,
            db=db,
            user_id=current_user["id"]
        )
        return None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating interaction decision: {str(e)}"
        )


@traceable
@router.get(
    "/health",
    summary="Health check endpoint",
    description="Check the health status of the Briefing Enhancer Service.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "service": "briefing-enhancer-service",
                        "version": "1.0.0"
                    }
                }
            }
        }
    },
    tags=["health"]
)
async def health_check():
    return {
        "status": "healthy",
        "service": "briefing-enhancer-service",
        "version": "1.0.0"
    }

