"""A2A Agent Card for the Legal Validation agent."""

from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from app.core.config import settings


def _a2a_url() -> str:
    base = (settings.A2A_BASE_URL or "").rstrip("/")
    return f"{base}/a2a" if base else "http://localhost:8005/a2a"


def build_agent_card() -> AgentCard:
    """Build the public Agent Card for legal validation (A2A discovery)."""
    skill = AgentSkill(
        id="validate-communication",
        name="Validar comunicação",
        description=(
            "Valida peças de comunicação (SMS, PUSH, E-mail, APP) em conformidade "
            "com diretrizes jurídicas. Retorna decisão (APROVADO/REPROVADO), "
            "se requer revisão humana, resumo e fontes."
        ),
        tags=[
            "legal",
            "validation",
            "compliance",
            "SMS",
            "PUSH",
            "EMAIL",
            "APP",
        ],
        examples=[
            '{"metadata":{"transaction_id":"...","timestamp":"...","source_system":"..."},"task":"VALIDATE_COMMUNICATION","channel":"SMS","payload_type":"INLINE","content":{"body":"..."}}',
            '{"task":"VALIDATE_COMMUNICATION","channel":"PUSH","payload_type":"INLINE","content":{"title":"...","body":"..."}}',
            '{"task":"VALIDATE_COMMUNICATION","channel":"EMAIL","payload_type":"INLINE","content":{"html":"<html>...</html>"}}',
            '{"task":"VALIDATE_COMMUNICATION","channel":"APP","payload_type":"INLINE","content":{"image":"data:image/png;base64,..."}}',
        ],
        input_modes=["application/json"],
        output_modes=["application/json"],
    )

    return AgentCard(
        name="Orqestra Legal Agent",
        description=(
            "Agente de validação jurídica de comunicações. Analisa conteúdo por canal "
            "(SMS, PUSH, E-mail, APP) conforme diretrizes e retorna parecer estruturado."
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
        preferred_transport="HTTP+JSON"
    )
