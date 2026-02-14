import logging
import re
from typing import Any
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import DataPart, Part
from a2a.utils.message import new_agent_parts_message
from pydantic import ValidationError as PydanticValidationError
from app.api.routes import get_agent
from app.api.schemas import (
    AppContent,
    EmailContent,
    PUSHContent,
    SMSContent,
    ValidateRequest,
)
from app.core.database import SessionLocal
from app.models.validation_audit import LegalValidationAudit

logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_data_part_json(context: RequestContext) -> dict:
    msg = context.message
    items = getattr(msg, "content", None) or getattr(msg, "parts", None) or []
    if not msg or not items:
        raise ValueError("Mensagem deve ter ao menos um part (content).")
    for p in items:
        root = getattr(p, "root", p)
        inner = getattr(root, "data", None)
        if inner is None:
            continue
        # Protobuf: Part.data = DataPart, DataPart.data = Struct (our payload).
        if isinstance(inner, dict):
            return inner
        if hasattr(inner, "data") and isinstance(getattr(inner, "data"), dict):
            return getattr(inner, "data")
    raise ValueError(
        "Envie um DataPart com JSON { metadata?, task, channel, payload_type, content } (ValidateRequest)."
    )


def _invoke_payload(data: ValidateRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    agent = get_agent()
    content_title = None
    content_body = None
    content_image = None

    if isinstance(data.content, PUSHContent):
        content_title = data.content.title
        content_body = data.content.body
    elif isinstance(data.content, SMSContent):
        content_body = data.content.body
    elif isinstance(data.content, EmailContent):

        if data.content.html:
            content_body = _strip_html(data.content.html)
        if data.content.image:
            content_image = data.content.image
        logger.info("EMAIL: html=%s, image=%s",
                   "yes" if data.content.html else "no",
                   "yes" if data.content.image else "no")
    elif isinstance(data.content, AppContent):
        content_image = data.content.image

    content_str = ""
    if content_title and content_body:
        content_str = f"{content_title}\n\n{content_body}"
    elif content_body:
        content_str = content_body
    
    if content_image and not content_body:
        content_str = f"[{data.channel} 1 imagem]"
    elif content_image and content_body:
        content_str = f"{content_body}\n[+ 1 imagem anexa]"

    result = agent.invoke(
        task=data.task,
        channel=data.channel,
        content=content_str or ("[APP 1 imagem]" if content_image else ""),
        content_title=content_title,
        content_body=content_body,
        content_image=content_image,
    )

    internal = result.pop("_internal", {})
    if not result.get("sources") and not internal.get("retrieved_chunks"):
        raise ValueError(
            "Nenhum documento encontrado no Weaviate. Execute a ingestão de documentos primeiro."
        )

    output = {
        "decision": result.get("decision", "REPROVADO"),
        "requires_human_review": result.get("requires_human_review", True),
        "summary": result.get("summary", ""),
        "sources": result.get("sources", []),
    }

    search_meta = internal.get("search_metadata") or {}
    llm_model = None
    if getattr(agent, "channel_to_model", None):

        if data.channel == "EMAIL" and content_image:
            llm_model = agent.channel_to_model.get("APP")
        else:
            llm_model = agent.channel_to_model.get(data.channel)
    if llm_model is None:
        llm_model = next(
            iter(getattr(agent, "channel_to_model", {}).values()),
            "sabiazinho-4",
        )

    audit_info = {
        "task": data.task,
        "channel": data.channel,
        "content_str": content_str,
        "content_hash": LegalValidationAudit.generate_content_hash(content_str),
        "num_chunks_retrieved": internal.get("num_chunks_retrieved"),
        "search_query": search_meta.get("query"),
        "llm_model": llm_model,
    }
    return output, audit_info


class LegalAgentExecutor(AgentExecutor):
    """A2A executor that runs legal validation and returns a Message with DataPart."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        try:
            raw = _extract_data_part_json(context)
            data = ValidateRequest.model_validate(raw)
        except PydanticValidationError as e:
            logger.warning("A2A ValidateRequest error: %s", e)
            raise ValueError(f"ValidateRequest inválido: {e}") from e
        except ValueError as e:
            raise

        try:
            output, audit_info = _invoke_payload(data)
        except ValueError as e:
            raise
        except Exception as e:
            logger.exception("A2A invoke error: %s", e)
            raise

        db = SessionLocal()
        try:
            audit = LegalValidationAudit(
                task=audit_info["task"],
                channel=audit_info["channel"],
                content_hash=audit_info["content_hash"],
                content_preview=(
                    audit_info["content_str"][:500]
                    if len(audit_info["content_str"]) > 500
                    else audit_info["content_str"]
                ),
                decision=output["decision"],
                requires_human_review=output["requires_human_review"],
                summary=output["summary"],
                sources=output["sources"],
                num_chunks_retrieved=audit_info["num_chunks_retrieved"],
                llm_model=audit_info["llm_model"],
                search_query=audit_info["search_query"],
            )
            db.add(audit)
            db.commit()
            logger.info("A2A message:send audit logged: id=%s", audit.id)
        except Exception as e:
            db.rollback()
            logger.exception("A2A audit error: %s", e)
        finally:
            db.close()

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
        raise NotImplementedError("Cancelamento não suportado para validação legal.")
