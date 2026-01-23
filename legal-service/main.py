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


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION
    }

