"""A2A Agent Card for the Content Validation orchestrator."""

from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from app.core.config import settings


def _a2a_url() -> str:
    base = (settings.A2A_BASE_URL or "").rstrip("/")
    return f"{base}/a2a" if base else "http://localhost:8004/a2a"


def build_agent_card() -> AgentCard:
    """Build the public Agent Card for content validation (A2A discovery)."""
    skill = AgentSkill(
        id="analyze-piece",
        name="Analisar peça",
        description=(
            "Orquestra a validação de peças de comunicação (SMS, PUSH, E-mail, APP): "
            "valida formato/tamanho, opcionalmente busca conteúdo via MCP, consulta Legal via A2A, "
            "emite veredito final. Retorna validation_result, compliance_result, final_verdict, etc."
        ),
        tags=[
            "content",
            "validation",
            "orchestrator",
            "SMS",
            "PUSH",
            "EMAIL",
            "APP",
        ],
        examples=[
            '{"task":"VALIDATE_COMMUNICATION","channel":"SMS","content":{"body":"Olá, teste."}}',
            '{"task":"VALIDATE_COMMUNICATION","channel":"PUSH","content":{"title":"Título","body":"Corpo"}}',
            '{"task":"VALIDATE_COMMUNICATION","channel":"EMAIL","content":{"campaign_id":"...","piece_id":"..."}}',
            '{"task":"VALIDATE_COMMUNICATION","channel":"APP","content":{"campaign_id":"...","piece_id":"...","commercial_space":"Home"}}',
        ],
        input_modes=["application/json"],
        output_modes=["application/json"],
    )

    return AgentCard(
        name="Orqestra Content Validation Agent",
        description=(
            "Orquestrador de validação de conteúdo. Valida formato/tamanho, "
            "busca peças (MCP), consulta Legal (A2A) e emite veredito final."
        ),
        url=_a2a_url(),
        version=settings.SERVICE_VERSION,
        protocol_version="1.0",
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=False,
        ),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[skill],
        preferred_transport="HTTP+JSON",
    )
