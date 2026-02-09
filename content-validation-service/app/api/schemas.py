from typing import Any, Dict, List, Literal, Optional

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
    """Response de /api/ai/analyze-piece.
    
    Fluxo paralelo:
    - validate_channel (estrutural) → retrieve_content (EMAIL/APP)
    - [specs, branding, compliance] executam em paralelo
    - issue_final_verdict agrega os 3 resultados
    
    Early-fail apenas em validate_channel ou retrieve_content.
    Use `failure_stage` (só para early-fails) e `stages_completed`.
    """

    validation_result: Dict[str, Any] = Field(
        ...,
        description="Resultado da validação de formato/tamanho (validate_channel)",
    )
    specs_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Resultado da validação de specs técnicos (dimensões, peso, caracteres)",
    )
    orchestration_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Resultado da orquestração (agregado de todas as etapas)",
    )
    compliance_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Parecer do Legal Service (A2A), quando aplicável",
    )
    branding_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Parecer do Branding Service (MCP) - validação determinística de marca (EMAIL/APP)",
    )
    requires_human_approval: bool = Field(
        False,
        description="True se o legal-service recomenda revisão humana",
    )
    human_approval_reason: Optional[str] = Field(
        None,
        description="Motivo da recomendação de revisão humana",
    )
    failure_stage: Optional[str] = Field(
        None,
        description="Estágio onde a validação falhou (fail-fast). None se passou em tudo.",
    )
    stages_completed: Optional[List[str]] = Field(
        None,
        description="Lista de estágios completados com sucesso antes de falhar ou finalizar.",
    )
    final_verdict: Optional[Dict[str, Any]] = Field(
        None,
        description="Veredito final: decision (APROVADO|REPROVADO), summary, failure_stage, stages_completed, specs, legal, branding",
    )
