from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class AnalyzePieceRequest(BaseModel):
    """Request para /api/ai/analyze-piece."""

    task: Literal["VALIDATE_COMMUNICATION"] = Field(
        default="VALIDATE_COMMUNICATION",
        description="Tipo de tarefa",
    )
    channel: Literal["SMS", "PUSH", "EMAIL", "APP"] = Field(
        ...,
        description="Canal da peça",
    )
    content: Dict[str, Any] = Field(
        ...,
        description="Conteúdo inline (SMS/PUSH) ou ref (EMAIL/APP): campaign_id, piece_id, commercial_space?",
    )
    campaign_id: Optional[str] = Field(
        None,
        description="Obrigatório para persistir parecer (SMS/PUSH). Usado em GET ao recarregar a página.",
    )


class AnalyzePieceResponse(BaseModel):
    """Response de /api/ai/analyze-piece."""

    validation_result: Dict[str, Any] = Field(
        ...,
        description="Resultado da validação de formato/tamanho (validate_channel)",
    )
    orchestration_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Resultado da orquestração (legado / agregado)",
    )
    compliance_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Parecer do Legal Service (A2A), quando aplicável",
    )
    requires_human_approval: bool = Field(
        False,
        description="True se retrieve ou validate_compliance falhou",
    )
    human_approval_reason: Optional[str] = Field(
        None,
        description="Motivo da aprovação humana",
    )
    final_verdict: Optional[Dict[str, Any]] = Field(
        None,
        description="Veredito final: status (approved|rejected), message, contributors (legal + futuros agentes)",
    )
