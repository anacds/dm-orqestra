from __future__ import annotations
import logging
from typing import Any
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import DataPart, Part
from a2a.utils.message import new_agent_parts_message
from pydantic import ValidationError as PydanticValidationError
from app.api.routes import get_agent
from app.api.schemas import AnalyzePieceRequest

logger = logging.getLogger(__name__)


def _extract_data_part_json(context: RequestContext) -> dict:
    """Extract AnalyzePieceRequest-shaped JSON from the user message's DataPart."""
    msg = context.message
    items = getattr(msg, "content", None) or getattr(msg, "parts", None) or []
    if not msg or not items:
        raise ValueError("Mensagem deve ter ao menos um part (content).")
    raw = None
    for p in items:
        root = getattr(p, "root", p)
        inner = getattr(root, "data", None)
        if inner is None:
            continue
        if isinstance(inner, dict):
            raw = inner
            break
        if hasattr(inner, "data") and isinstance(getattr(inner, "data"), dict):
            raw = getattr(inner, "data")
            break
    if raw is None:
        raise ValueError(
            "Envie um DataPart com JSON { task?, channel, content } (AnalyzePieceRequest)."
        )
    # Support nested data.data (A2A wire format)
    if isinstance(raw.get("data"), dict) and set(raw.keys()) <= {"data"}:
        return raw["data"]
    return raw


async def _invoke_payload(data: AnalyzePieceRequest) -> dict[str, Any]:
    """Run ContentValidationAgent.ainvoke and return response dict for A2A DataPart."""
    agent = get_agent()
    result = await agent.ainvoke(
        task=data.task,
        channel=data.channel,
        content=data.content,
    )
    return {
        "validation_result": result.get("validation_result") or {},
        "orchestration_result": result.get("orchestration_result"),
        "compliance_result": result.get("compliance_result"),
        "requires_human_approval": result.get("requires_human_approval", False),
        "human_approval_reason": result.get("human_approval_reason"),
        "final_verdict": result.get("final_verdict"),
    }


class ContentValidationAgentExecutor(AgentExecutor):
    """A2A executor that runs content validation and returns a Message with DataPart."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        try:
            raw = _extract_data_part_json(context)
            data = AnalyzePieceRequest.model_validate(raw)
        except PydanticValidationError as e:
            logger.warning("A2A AnalyzePieceRequest error: %s", e)
            raise ValueError(f"AnalyzePieceRequest inválido: {e}") from e
        except ValueError:
            raise

        try:
            output = await _invoke_payload(data)
        except ValueError:
            raise
        except Exception as e:
            logger.exception("A2A invoke error: %s", e)
            raise

        part = Part(root=DataPart(data=output))
        msg = new_agent_parts_message(
            parts=[part],
            context_id=context.context_id,
            task_id=context.task_id,
        )
        await event_queue.enqueue_event(msg)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise NotImplementedError("Cancelamento não suportado para content validation.")
