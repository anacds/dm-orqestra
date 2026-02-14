import contextlib
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

from app.client import fetch_piece_content
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "campaigns-mcp-server",
    instructions="MCP server que expõe o download de peças criativas (HTML ou imagem) do campaigns-service.",
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def retrieve_piece_content(
    campaign_id: str,
    piece_id: str,
    commercial_space: Optional[str] = None,
) -> dict:
    """
    Busca o conteúdo de uma peça criativa (E-mail ou App) no campaigns-service.

    - E-mail: retorna HTML (contentType text/html, content como string JSON-safe).
    - App: requer commercial_space; retorna imagem em base64 (content como data URL).

    Args:
        campaign_id: ID da campanha.
        piece_id: ID da peça (CreativePiece), obtido no response do upload ou em GET campaign.
        commercial_space: Obrigatório para peças App; use o espaço comercial (ex: Home).
    """
    data = await fetch_piece_content(campaign_id, piece_id, commercial_space)
    # Normalize keys for consistent JSON (campaigns may return contentType)
    return {
        "contentType": data.get("contentType") or data.get("content_type", "application/octet-stream"),
        "content": data.get("content", ""),
    }


@contextlib.asynccontextmanager
async def _lifespan(_app: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[Mount("/", app=mcp.streamable_http_app())],
    lifespan=_lifespan,
)


def main() -> None:
    import uvicorn

    s = get_settings()
    logger.info(
        "Starting campaigns-mcp-server at 0.0.0.0:%s (campaigns=%s)",
        s.port,
        s.campaigns_service_url,
    )
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=s.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
