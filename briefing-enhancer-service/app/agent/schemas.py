from pydantic import BaseModel, Field

class EnhancedTextResponse(BaseModel):
    """Response schema for enhanced text with explanation."""
    enhanced_text: str = Field(description="O texto melhorado")
    explanation: str = Field(description="Explicação sobre as melhorias aplicadas")

