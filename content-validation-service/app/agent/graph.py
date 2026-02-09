import logging
import time
from typing import Any, Optional
from langgraph.graph import END, StateGraph
from app.agent.state import ValidationGraphState
from app.agent.nodes import (
    issue_final_verdict_node,
    retrieve_content_node,
    validate_channel_node,
    validate_compliance_node,
    validate_branding_node,
    validate_specs_node,
)
from app.core.metrics import VALIDATION_TOTAL, VALIDATION_DURATION

logger = logging.getLogger(__name__)


# ==========================================================================
# Fluxo do grafo (máximo paralelo):
#
#   validate_channel
#     ├─ SMS/PUSH OK  → [specs, branding, compliance] (3 em paralelo)
#     ├─ EMAIL/APP OK → retrieve_content
#     └─ fail         → issue_final_verdict
#
#   retrieve_content
#     ├─ OK   → [specs, branding, compliance] (3 em paralelo)
#     └─ fail → issue_final_verdict
#
#   validate_specs      ─┐
#   validate_branding   ─┤→ issue_final_verdict (espera os 3)
#   validate_compliance ─┘
#
#   issue_final_verdict: agrega os 3 resultados → decisão final → END
#
#   Dependências reais de dados:
#   - specs      precisa de: content | content_for_compliance, conversion_metadata
#   - branding   precisa de: html_for_branding | image_for_branding
#   - compliance precisa de: content_for_compliance, channel
#   Todos esses campos são preenchidos por validate_channel (SMS/PUSH)
#   ou retrieve_content (EMAIL/APP), portanto os 3 podem rodar em paralelo.
# ==========================================================================


_PARALLEL_NODES = ["validate_specs", "validate_branding", "validate_compliance"]


def _route_after_validate_channel(state: ValidationGraphState) -> Any:
    channel = (state.get("channel") or "").upper()
    valid = state.get("validation_valid", False)

    if channel in ("SMS", "PUSH"):
        if valid:
            return _PARALLEL_NODES
        return "issue_final_verdict"

    if channel in ("EMAIL", "APP"):
        if valid:
            return "retrieve_content"
        return "issue_final_verdict"

    return "issue_final_verdict"


def _route_after_retrieve(state: ValidationGraphState) -> Any:
    """Após retrieve: OK → [specs, branding, compliance] em paralelo; fail → verdict."""
    if state.get("retrieve_ok"):
        return _PARALLEL_NODES
    return "issue_final_verdict"


class ContentValidationAgent:

    def __init__(self) -> None:
        self.graph_builder = self._build_graph()
        self.app = self.graph_builder.compile()
        logger.info("ContentValidationAgent initialized (LangGraph)")

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ValidationGraphState)

        workflow.add_node("validate_channel", validate_channel_node)
        workflow.add_node("retrieve_content", retrieve_content_node)
        workflow.add_node("validate_specs", validate_specs_node)
        workflow.add_node("validate_branding", validate_branding_node)
        workflow.add_node("validate_compliance", validate_compliance_node)
        workflow.add_node("issue_final_verdict", issue_final_verdict_node)

        workflow.set_entry_point("validate_channel")

        # validate_channel → [specs, branding, compliance] | retrieve | verdict
        workflow.add_conditional_edges(
            "validate_channel",
            _route_after_validate_channel,
            {
                "validate_specs": "validate_specs",
                "validate_branding": "validate_branding",
                "validate_compliance": "validate_compliance",
                "retrieve_content": "retrieve_content",
                "issue_final_verdict": "issue_final_verdict",
            },
        )

        # retrieve → [specs, branding, compliance] | verdict
        workflow.add_conditional_edges(
            "retrieve_content",
            _route_after_retrieve,
            {
                "validate_specs": "validate_specs",
                "validate_branding": "validate_branding",
                "validate_compliance": "validate_compliance",
                "issue_final_verdict": "issue_final_verdict",
            },
        )

        # Os 3 nós convergem para issue_final_verdict (LangGraph espera todos)
        workflow.add_edge("validate_specs", "issue_final_verdict")
        workflow.add_edge("validate_branding", "issue_final_verdict")
        workflow.add_edge("validate_compliance", "issue_final_verdict")

        workflow.add_edge("issue_final_verdict", END)

        return workflow

    def invoke(
        self,
        task: Optional[str] = None,
        channel: Optional[str] = None,
        content: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Executa o grafo de validação."""
        initial: ValidationGraphState = {
            "task": task or "VALIDATE_COMMUNICATION",
            "channel": channel or "",
            "content": content or {},
            "validation_result": None,
            "validation_valid": False,
            "retrieve_ok": False,
            "retrieve_error": None,
            "content_for_compliance": None,
            "html_for_branding": None,
            "image_for_branding": None,
            "conversion_metadata": None,
            "specs_ok": None,
            "specs_result": None,
            "compliance_ok": False,
            "compliance_result": None,
            "compliance_error": None,
            "branding_ok": None,
            "branding_result": None,
            "branding_error": None,
            "requires_human_approval": False,
            "human_approval_reason": None,
            "final_verdict": None,
            "orchestration_result": None,
        }

        logger.info("Invoking content-validation graph: task=%s, channel=%s", task, channel)
        result = self.app.invoke(initial)
        return dict(result)

    async def ainvoke(
        self,
        task: Optional[str] = None,
        channel: Optional[str] = None,
        content: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        initial: ValidationGraphState = {
            "task": task or "VALIDATE_COMMUNICATION",
            "channel": channel or "",
            "content": content or {},
            "validation_result": None,
            "validation_valid": False,
            "retrieve_ok": False,
            "retrieve_error": None,
            "content_for_compliance": None,
            "html_for_branding": None,
            "image_for_branding": None,
            "conversion_metadata": None,
            "specs_ok": None,
            "specs_result": None,
            "compliance_ok": False,
            "compliance_result": None,
            "compliance_error": None,
            "branding_ok": None,
            "branding_result": None,
            "branding_error": None,
            "requires_human_approval": False,
            "human_approval_reason": None,
            "final_verdict": None,
            "orchestration_result": None,
        }
        ch = (channel or "unknown").upper()
        logger.info("Invoking content-validation graph (async): task=%s, channel=%s", task, channel)
        start = time.perf_counter()
        result = await self.app.ainvoke(initial)
        elapsed = time.perf_counter() - start
        VALIDATION_DURATION.labels(channel=ch).observe(elapsed)
        verdict = (result.get("final_verdict") or {}).get("decision", "unknown")
        VALIDATION_TOTAL.labels(channel=ch, verdict=verdict).inc()
        return dict(result)

graph = ContentValidationAgent().app
