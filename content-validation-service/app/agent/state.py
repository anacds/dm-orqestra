from typing import TypedDict, Optional, Any


class ValidationGraphState(TypedDict, total=False):
    """State do grafo de validação de conteúdo (orquestrador)."""

    task: Optional[str]
    channel: Optional[str]
    content: Optional[dict]

    validation_result: Optional[dict]
    validation_valid: bool

    retrieve_ok: bool
    retrieve_error: Optional[str]
    content_for_compliance: Optional[dict]

    compliance_ok: bool
    compliance_result: Optional[dict]
    compliance_error: Optional[str]

    requires_human_approval: bool
    human_approval_reason: Optional[str]

    final_verdict: Optional[dict]
    orchestration_result: Optional[dict]
