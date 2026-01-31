"""
Branding Service - Entry point.

Serviço de validação determinística de marca para emails HTML.
Exposto via MCP (Model Context Protocol).
"""

import contextlib
import logging

from starlette.applications import Starlette
from starlette.routing import Mount

from app.core.config import get_settings
from app.mcp.server import mcp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    """Application lifespan handler."""
    logger.info("Starting Branding Service...")
    async with mcp.session_manager.run():
        yield
    logger.info("Shutting down Branding Service...")


app = Starlette(
    routes=[Mount("/", app=mcp.streamable_http_app())],
    lifespan=lifespan,
)


def main() -> None:
    """Run the server."""
    import uvicorn

    settings = get_settings()
    logger.info("Starting branding-service at 0.0.0.0:%s", settings.port)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
