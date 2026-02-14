import base64
import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.s3_client import get_file
from app.core.metrics import MCP_TOOL_CALLS
from app.models.creative_piece import CreativePiece
from app.models.channel_spec import ChannelSpec
from app.services.file_upload import extract_file_key_from_url, get_app_file_urls_dict

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "campaigns-mcp-server",
    instructions=(
        "MCP server integrado ao campaigns-service. "
        "Expõe download de peças criativas (HTML ou imagem) e specs técnicos de canais."
    ),
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def retrieve_piece_content(
    campaign_id: str,
    piece_id: str,
    commercial_space: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Busca o conteúdo de uma peça criativa (E-mail ou App).

    - E-mail: retorna HTML (contentType text/html, content como string).
    - App: requer commercial_space; retorna imagem em base64 (content como data URL).

    Args:
        campaign_id: ID da campanha.
        piece_id: ID da peça (CreativePiece).
        commercial_space: Obrigatório para peças App.
    """
    MCP_TOOL_CALLS.labels(tool_name="retrieve_piece_content").inc()
    db = SessionLocal()
    try:
        piece = (
            db.query(CreativePiece)
            .filter(
                CreativePiece.campaign_id == campaign_id,
                CreativePiece.id == piece_id,
            )
            .first()
        )

        if not piece:
            return {"error": f"Piece {piece_id} not found in campaign {campaign_id}"}

        if piece.piece_type == "E-mail":
            if not piece.html_file_url:
                return {"error": "Email piece has no HTML file"}
            file_key = extract_file_key_from_url(piece.html_file_url, settings.S3_BUCKET_NAME)
            if not file_key:
                return {"error": "Invalid HTML file URL"}
            body, content_type = get_file(file_key)
            try:
                html = body.decode("utf-8")
            except UnicodeDecodeError:
                html = body.decode("latin-1")
            return {"contentType": content_type, "content": html}

        if piece.piece_type == "App":
            if not commercial_space:
                return {"error": "commercial_space is required for App pieces"}
            urls_dict = get_app_file_urls_dict(piece.file_urls)
            file_url = urls_dict.get(commercial_space)
            if not file_url:
                return {"error": f"No file for commercial space: {commercial_space}"}
            file_key = extract_file_key_from_url(file_url, settings.S3_BUCKET_NAME)
            if not file_key:
                return {"error": "Invalid file URL"}
            body, content_type = get_file(file_key)
            b64 = base64.b64encode(body).decode("ascii")
            data_url = f"data:{content_type};base64,{b64}"
            return {"contentType": content_type, "content": data_url}

        return {"error": f"Download not supported for piece type: {piece.piece_type}"}
    except Exception as e:
        logger.exception("retrieve_piece_content error: %s", e)
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
async def get_channel_specs(
    channel: str,
    commercial_space: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retorna as especificações técnicas de um canal e espaço comercial.

    Inclui limites de caracteres, peso de arquivo e dimensões de imagem.
    Para APP com commercial_space, retorna specs específicos do espaço.

    Args:
        channel: Canal (SMS, PUSH, EMAIL ou APP).
        commercial_space: Espaço comercial (opcional, usado para APP).

    Returns:
        Dict com specs por field_name. Exemplo:
        {
            "channel": "APP",
            "commercial_space": "Banner superior da Home",
            "specs": {
                "image": {
                    "max_weight_kb": 300,
                    "expected_width": 1200,
                    "expected_height": 628,
                    "tolerance_pct": 5
                }
            },
            "generic_specs": {
                "image": {
                    "max_weight_kb": 1024,
                    "min_width": 300, "min_height": 300,
                    "max_width": 4096, "max_height": 4096
                }
            }
        }
    """
    MCP_TOOL_CALLS.labels(tool_name="get_channel_specs").inc()
    channel_upper = channel.upper().replace("-", "").replace(" ", "")
    if channel_upper == "E-MAIL":
        channel_upper = "EMAIL"

    db = SessionLocal()
    try:
        generic_rows = (
            db.query(ChannelSpec)
            .filter(
                ChannelSpec.channel == channel_upper,
                ChannelSpec.commercial_space.is_(None),
                ChannelSpec.active.is_(True),
            )
            .all()
        )

        generic_specs = {}
        for row in generic_rows:
            generic_specs[row.field_name] = _row_to_dict(row)

        # Specs do espaço comercial (se informado)
        space_specs = {}
        if commercial_space:
            space_rows = (
                db.query(ChannelSpec)
                .filter(
                    ChannelSpec.channel == channel_upper,
                    ChannelSpec.commercial_space == commercial_space,
                    ChannelSpec.active.is_(True),
                )
                .all()
            )
            for row in space_rows:
                space_specs[row.field_name] = _row_to_dict(row)

        return {
            "channel": channel_upper,
            "commercial_space": commercial_space,
            "specs": space_specs if space_specs else generic_specs,
            "generic_specs": generic_specs,
        }
    except Exception as e:
        logger.exception("get_channel_specs error: %s", e)
        return {"error": str(e), "channel": channel_upper, "specs": {}, "generic_specs": {}}
    finally:
        db.close()


def _row_to_dict(row: ChannelSpec) -> Dict[str, Any]:
    """Converte um ChannelSpec row para dict (somente campos com valor)."""
    result: Dict[str, Any] = {}
    for attr in (
        "min_chars", "max_chars", "warn_chars",
        "max_weight_kb",
        "min_width", "min_height", "max_width", "max_height",
        "expected_width", "expected_height", "tolerance_pct",
    ):
        val = getattr(row, attr, None)
        if val is not None:
            result[attr] = val
    return result


def build_mcp_app() -> Starlette:
    """Build Starlette app with MCP routes."""
    return Starlette(
        routes=[Mount("/", app=mcp.streamable_http_app())],
    )
