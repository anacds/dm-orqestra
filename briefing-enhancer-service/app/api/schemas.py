from pydantic import BaseModel, Field
from typing import Optional, Literal


class EnhanceObjectiveRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text to enhance. Maximum length is 5000 characters.",
        example="Aumentar as vendas do produto X"
    )
    field_name: str = Field(
        ...,
        description="Name of the field to enhance. Supported values: 'businessObjective', 'expectedResult', 'targetAudienceDescription', 'exclusionCriteria'",
        example="businessObjective"
    )
    campaign_id: Optional[str] = Field(
        None,
        description="Campaign ID if available. Can be null during campaign creation.",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier to group interactions from the same session. Useful for tracking multiple enhancements in a single campaign creation flow.",
        example="session_1234567890_abc123"
    )
    campaign_name: Optional[str] = Field(
        None,
        description="Campaign name/title. Optional, but helps provide context for enhancement.",
        example="Campanha de Retenção Q1 2024"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Aumentar as vendas",
                    "field_name": "businessObjective",
                    "campaign_id": None,
                    "session_id": "session_1234567890_abc123"
                }
            ]
        }
    }


class EnhanceObjectiveResponse(BaseModel):
    enhanced_text: str = Field(
        ...,
        alias="enhancedText",
        description="The enhanced version of the input text, improved for clarity, specificity, and structure.",
        example="Aumentar as vendas do produto X em 15% no trimestre Q2 de 2024, focando em novos clientes na região Sudeste."
    )
    explanation: str = Field(
        ...,
        description="Detailed explanation of the improvements made to the text, including what was changed and why.",
        example="O texto foi aprimorado adicionando métricas específicas (15%), prazo definido (Q2 2024), segmento de clientes (novos clientes) e região geográfica (Sudeste), tornando o objetivo mensurável e acionável."
    )
    interaction_id: str = Field(
        ...,
        alias="interactionId",
        description="Unique identifier for this AI interaction. Use this ID to update the user decision (approved/rejected) later.",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    
    model_config = {"populate_by_name": True}


class UpdateInteractionDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"] = Field(
        ...,
        description="User's decision on the AI enhancement. Use 'approved' if the enhancement was accepted, or 'rejected' if it was not used.",
        example="approved"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "decision": "approved"
                },
                {
                    "decision": "rejected"
                }
            ]
        }
    }

