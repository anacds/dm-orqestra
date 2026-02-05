import warnings

# Suprime deprecation warning da biblioteca a2a (HTTP_413_REQUEST_ENTITY_TOO_LARGE)
# TODO: Remover quando a2a for atualizada
warnings.filterwarnings(
    "ignore",
    message=".*HTTP_413_REQUEST_ENTITY_TOO_LARGE.*",
    category=DeprecationWarning,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.api.routes import router, get_agent
from app.a2a.app import build_a2a_app

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Legal Service...")
    try:
        logger.info("Legal agent will be initialized on first use")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
    yield
    logger.info("Shutting down Legal Service...")
    try:
        agent = get_agent()
        if agent:
            agent.close()
    except Exception:
        pass


app = FastAPI(
    title="Orqestra Legal Service",
    description="AI-powered legal validation service for communications using RAG and LangGraph.",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/legal", tags=["legal"])

# A2A Protocol (independent of REST). Mount at /a2a so that:
# - GET  /a2a/.well-known/agent-card.json
# - POST /a2a/v1/message:send ou /a2a/v1/message/send
a2a_app = build_a2a_app()
app.mount("/a2a", a2a_app)

