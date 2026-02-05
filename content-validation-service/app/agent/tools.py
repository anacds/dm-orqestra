from __future__ import annotations
import json
import logging
import uuid
from typing import Any, Optional
import httpx
from langchain_core.tools import tool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.client.sse import sse_client
from app.core.config import settings

logger = logging.getLogger(__name__)


@tool
async def retrieve_piece_content(
    campaign_id: str,
    piece_id: str,
    commercial_space: Optional[str] = None,
) -> dict:
    """
    Busca conteúdo de uma peça criativa via campaigns-mcp-server (MCP).

    Use esta tool para obter o conteúdo de peças EMAIL ou APP que estão
    armazenadas no S3/LocalStack.

    Args:
        campaign_id: ID da campanha
        piece_id: ID da peça criativa
        commercial_space: Espaço comercial (obrigatório para APP)

    Returns:
        Dict com contentType e content (HTML escapado ou data URL base64).
    """
    url = f"{settings.CAMPAIGNS_MCP_URL.rstrip('/')}/mcp"
    arguments: dict[str, Any] = {"campaign_id": campaign_id, "piece_id": piece_id}
    if commercial_space is not None:
        arguments["commercial_space"] = commercial_space

    logger.info(
        "retrieve_piece_content: campaign_id=%s, piece_id=%s, commercial_space=%s",
        campaign_id,
        piece_id,
        commercial_space,
    )

    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("retrieve_piece_content", arguments=arguments)

    if getattr(result, "is_error", False):
        err_msg = _format_mcp_error(result)
        logger.warning("retrieve_piece_content MCP error: %s", err_msg)
        raise RuntimeError(err_msg)

    data = _parse_mcp_result(result)
    return {
        "contentType": data.get("contentType") or data.get("content_type", "application/octet-stream"),
        "content": data.get("content", ""),
    }


def _format_mcp_error(result: Any) -> str:
    content = getattr(result, "content", None) or []
    parts = []
    for c in content if isinstance(content, list) else []:
        t = getattr(c, "text", None)
        if t:
            parts.append(str(t))
    if parts:
        return " ".join(parts).strip() or "retrieve_piece_content failed"
    return "retrieve_piece_content failed (no detail)"


def _parse_mcp_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured

    content = getattr(result, "content", None) or []
    if isinstance(content, list) and content:
        first = content[0]
        text = getattr(first, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"content": text, "contentType": "text/plain"}

    return {}


def _build_legal_content(channel: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Monta content no formato esperado pelo Legal (ValidateRequest)."""
    if channel == "SMS":
        return {"body": str(payload.get("body", ""))}
    if channel == "PUSH":
        return {
            "title": str(payload.get("title", "")),
            "body": str(payload.get("body", "")),
        }
    if channel == "EMAIL":
        result: dict[str, Any] = {}
        if "html" in payload and payload.get("html"):
            result["html"] = str(payload["html"])
        if "image" in payload and payload.get("image"):
            result["image"] = str(payload["image"])
        return result if result else {"html": ""}
    if channel == "APP":
        return {"image": str(payload.get("image", ""))}
    return {}


@tool
async def validate_legal_compliance(
    channel: str,
    content: dict,
    task: str = "VALIDATE_COMMUNICATION",
) -> dict:
    """
    Valida conformidade legal de uma peça criativa via Legal Service (A2A).

    Envia o conteúdo para o agente jurídico que analisa se atende às
    diretrizes de comunicação da empresa.

    Args:
        channel: Canal da comunicação (SMS, PUSH, EMAIL, APP)
        content: Conteúdo a validar. Formato depende do canal:
            - SMS: {"body": "..."}
            - PUSH: {"title": "...", "body": "..."}
            - EMAIL: {"html": "..."}
            - APP: {"image": "data:image/png;base64,..."}
        task: Tipo de tarefa (default: VALIDATE_COMMUNICATION)

    Returns:
        Dict com decision (APROVADO/REPROVADO), requires_human_review,
        summary e sources.
    """
    base = settings.LEGAL_SERVICE_URL.rstrip("/")
    url = f"{base}/a2a/v1/message:send"
    inner = _build_legal_content(channel, content)

    request_data = {
        "task": task,
        "channel": channel,
        "payload_type": "INLINE",
        "content": inner,
    }

    payload = {
        "message": {
            "messageId": f"cvs-{uuid.uuid4().hex[:12]}",
            "role": 1,
            "content": [
                {
                    "data": {
                        "data": request_data
                    }
                }
            ],
        }
    }

    logger.info("validate_legal_compliance: channel=%s, task=%s", channel, task)

    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    out = _parse_a2a_response(data)
    if not out:
        raise RuntimeError("Legal A2A response sem content data")
    return out


def _parse_a2a_response(data: dict[str, Any]) -> dict[str, Any] | None:
    """Extrai o DataPart (decision, requires_human_review, summary, sources) da resposta."""
    msg = data.get("message") or data
    content = msg.get("content") or msg.get("parts") or []
    for p in content:
        node = p.get("root") or p.get("data") or p
        if not isinstance(node, dict):
            continue
        inner = node.get("data")
        if isinstance(inner, dict):
            if "decision" in inner:
                return inner
            nested = inner.get("data")
            if isinstance(nested, dict):
                return nested
            return inner
    return None


@tool
async def validate_brand_compliance(
    html: str,
) -> dict:
    """
    Valida conformidade de marca em HTML de email via branding-service (MCP).

    Executa validações determinísticas (sem IA/LLM) contra as diretrizes
    de marca da Orqestra: cores, tipografia, logo, layout, CTAs, footer.

    Args:
        html: Conteúdo HTML do email a ser validado

    Returns:
        Dict com:
        - compliant: bool - se está em conformidade
        - score: int - pontuação 0-100
        - violations: lista de violações encontradas
        - summary: contagem por severidade
    """
    url = f"{settings.BRANDING_MCP_URL.rstrip('/')}/mcp"
    arguments: dict[str, Any] = {"html": html}

    logger.info("validate_brand_compliance: html_length=%d", len(html))

    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("validate_email_brand", arguments=arguments)

    if getattr(result, "is_error", False):
        err_msg = _format_mcp_error(result)
        logger.warning("validate_brand_compliance MCP error: %s", err_msg)
        raise RuntimeError(err_msg)

    data = _parse_mcp_result(result)
    return {
        "compliant": data.get("compliant", False),
        "score": data.get("score", 0),
        "violations": data.get("violations", []),
        "summary": data.get("summary", {}),
    }


@tool
async def convert_html_to_image(
    html_content: str,
    scale: float = 0.3,
    image_format: str = "PNG",
) -> dict:
    """
    Converte conteúdo HTML em imagem Base64 via html-converter-service (MCP).

    Use esta tool para converter HTML de emails ou páginas web em uma imagem
    que pode ser analisada visualmente pelo modelo.

    Args:
        html_content: Conteúdo HTML a ser convertido (pode ser HTML5 ou fragmento)
        scale: Fator de escala da imagem (0.5 = 50% do tamanho original)
        image_format: Formato de saída (PNG ou JPEG)

    Returns:
        Dict com:
        - success: bool indicando sucesso
        - base64Image: imagem em Base64
        - imageFormat: formato da imagem
        - originalWidth/originalHeight: dimensões originais
        - reducedWidth/reducedHeight: dimensões após escala
        - fileSizeBytes: tamanho do arquivo
    """
    url = f"{settings.HTML_CONVERTER_MCP_URL.rstrip('/')}/sse"
    arguments: dict[str, Any] = {
        "htmlContent": html_content,
        "scale": scale,
        "imageFormat": image_format.upper(),
    }

    logger.info(
        "convert_html_to_image: html_length=%d, scale=%s, format=%s",
        len(html_content),
        scale,
        image_format,
    )

    async with sse_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("convert_html_to_image", arguments=arguments)

    if getattr(result, "is_error", False):
        err_msg = _format_mcp_error(result)
        logger.warning("convert_html_to_image MCP error: %s", err_msg)
        raise RuntimeError(err_msg)

    data = _parse_mcp_result(result)
    
    if not data.get("success", False):
        error = data.get("error", "Unknown error")
        logger.warning("convert_html_to_image failed: %s", error)
        raise RuntimeError(f"HTML conversion failed: {error}")

    return {
        "success": True,
        "base64Image": data.get("base64Image", ""),
        "imageFormat": data.get("imageFormat", image_format.upper()),
        "originalWidth": data.get("originalWidth", 0),
        "originalHeight": data.get("originalHeight", 0),
        "reducedWidth": data.get("reducedWidth", 0),
        "reducedHeight": data.get("reducedHeight", 0),
        "fileSizeBytes": data.get("fileSizeBytes", 0),
    }
