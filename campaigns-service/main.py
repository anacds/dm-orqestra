import contextlib
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router
from app.core.config import settings
from app.core.s3_client import ensure_bucket_exists
from app.mcp.server import mcp
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_bucket_exists()
    except Exception as e:
        logger.warning("could not initialize s3 bucket: %s", e)

    logger.info("Starting MCP session manager...")
    async with mcp.session_manager.run():
        yield

    logger.info("Shutting down campaigns-service...")


app = FastAPI(
    title="Orqestra Campaigns Service",
    description="Campaign Management API + MCP Server",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/campaigns", tags=["campaigns"])

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/health", "/api/health"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.mount("/", mcp.streamable_http_app())

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME, "mcp": "enabled"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running",
        "mcp_endpoint": "/mcp",
    }
