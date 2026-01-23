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
from app.core.checkpointer import close_checkpoint_pool
from app.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Briefing Enhancer Service...")
    try:
        logger.info("Checkpointing will be initialized on first use")
    except Exception as e:
        logger.error(f"Failed to initialize checkpointing: {e}")
    yield
    logger.info("Shutting down Briefing Enhancer Service...")
    await close_checkpoint_pool()


app = FastAPI(
    title="Orqestra Briefing Enhancer Service",
    description="AI-powered text enhancement service for campaign briefings using LangGraph and OpenAI.",
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

app.include_router(router, prefix="/api", tags=["ai"])


@app.get(
    "/",
    summary="Root endpoint",
    description="Get basic service information",
    tags=["health"]
)
async def root():
    """
    Basic service information
    """
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }

