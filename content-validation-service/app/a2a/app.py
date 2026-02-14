import logging
from a2a.server.apps.rest.fastapi_app import A2ARESTFastAPIApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from app.a2a.card import build_agent_card
from app.a2a.executor import ContentValidationAgentExecutor

logger = logging.getLogger(__name__)


def build_a2a_app():
    card = build_agent_card()
    task_store = InMemoryTaskStore()
    executor = ContentValidationAgentExecutor()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )

    a2a_app = A2ARESTFastAPIApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    _adapter = a2a_app._adapter
    _orig_routes = _adapter.routes

    def _routes_with_slash_alias():
        r = _orig_routes()
        key = ("/v1/message:send", "POST")
        if key in r:
            r[("/v1/message/send", "POST")] = r[key]
        return r

    _adapter.routes = _routes_with_slash_alias

    fastapi_app = a2a_app.build(
        agent_card_url="/.well-known/agent-card.json",
        rpc_url="",
    )
    logger.info(
        "A2A app built: GET /a2a/.well-known/agent-card.json, "
        "POST /a2a/v1/message:send and /a2a/v1/message/send"
    )
    return fastapi_app
