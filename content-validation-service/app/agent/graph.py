import logging
from typing import Any, Optional
from langgraph.graph import END, StateGraph
from app.agent.state import ValidationGraphState
from app.agent.nodes import (
    issue_final_verdict_node,
    retrieve_content_node,
    validate_channel_node,
    validate_compliance_node,
    validate_branding_node,
)

logger = logging.getLogger(__name__)


def _route_after_validate_channel(state: ValidationGraphState) -> Any:
    channel = (state.get("channel") or "").upper()
    valid = state.get("validation_valid", False)

    if channel in ("SMS", "PUSH"):
        if valid:
            return "validate_compliance"
        return END

    if channel in ("EMAIL", "APP"):
        return "retrieve_content"

    return END


def _route_after_retrieve(state: ValidationGraphState) -> Any:
    if state.get("retrieve_ok"):
        return "validate_compliance"
    return END


def _route_after_compliance(state: ValidationGraphState) -> Any:
    """Após compliance, EMAIL vai para branding; outros vão direto para verdict."""
    if not state.get("compliance_ok"):
        return END
    
    channel = (state.get("channel") or "").upper()
    html_for_branding = state.get("html_for_branding")
    
    # EMAIL com HTML vai para branding validation
    if channel == "EMAIL" and html_for_branding:
        return "validate_branding"
    
    # Outros canais (SMS, PUSH, APP) vão direto para verdict
    return "issue_final_verdict"


def _route_after_branding(state: ValidationGraphState) -> Any:
    """Após branding, vai para final verdict."""
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
        workflow.add_node("validate_compliance", validate_compliance_node)
        workflow.add_node("validate_branding", validate_branding_node)
        workflow.add_node("issue_final_verdict", issue_final_verdict_node)

        workflow.set_entry_point("validate_channel")

        workflow.add_conditional_edges(
            "validate_channel",
            _route_after_validate_channel,
            {
                "validate_compliance": "validate_compliance",
                "retrieve_content": "retrieve_content",
                END: "__end__",
            },
        )
        workflow.add_conditional_edges(
            "retrieve_content",
            _route_after_retrieve,
            {"validate_compliance": "validate_compliance", END: "__end__"},
        )
        workflow.add_conditional_edges(
            "validate_compliance",
            _route_after_compliance,
            {
                "validate_branding": "validate_branding",
                "issue_final_verdict": "issue_final_verdict",
                END: "__end__",
            },
        )
        workflow.add_conditional_edges(
            "validate_branding",
            _route_after_branding,
            {"issue_final_verdict": "issue_final_verdict"},
        )
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
            "compliance_ok": False,
            "compliance_result": None,
            "compliance_error": None,
            "branding_ok": False,
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
            "compliance_ok": False,
            "compliance_result": None,
            "compliance_error": None,
            "branding_ok": False,
            "branding_result": None,
            "branding_error": None,
            "requires_human_approval": False,
            "human_approval_reason": None,
            "final_verdict": None,
            "orchestration_result": None,
        }
        logger.info("Invoking content-validation graph (async): task=%s, channel=%s", task, channel)
        result = await self.app.ainvoke(initial)
        return dict(result)

graph = ContentValidationAgent().app
