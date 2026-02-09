import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router, router_ai
from app.a2a.app import build_a2a_app
from app.core.config import settings
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Content Validation Service",
    description="Orchestrator for content validation. Uses LangGraph (validate format/size, then orchestrate).",
    version=settings.SERVICE_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/content-validation", tags=["content-validation"])
app.include_router(router_ai, prefix="/api", tags=["ai"])

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# A2A Protocol (independent of REST). Mount at /a2a:
# GET /a2a/.well-known/agent-card.json | POST /a2a/v1/message:send or /a2a/v1/message/send
a2a_app = build_a2a_app()
app.mount("/a2a", a2a_app)


@app.get("/")
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running",
    }
