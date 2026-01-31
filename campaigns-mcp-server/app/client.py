"""HTTP client to call campaigns-service download endpoint."""

import base64
import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _to_ascii_safe(value: str) -> str:
    """Encode non-ASCII header values as base64 (same as api-gateway)."""
    if not value:
        return ""
    try:
        value.encode("ascii")
        return value
    except UnicodeEncodeError:
        encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
        return f"base64:{encoded}"


def _service_headers() -> dict[str, str]:
    s = get_settings()
    return {
        "X-User-Id": _to_ascii_safe(s.service_user_id),
        "X-User-Email": _to_ascii_safe(s.service_user_email),
        "X-User-Role": _to_ascii_safe(s.service_user_role),
        "X-User-Is-Active": s.service_user_is_active,
    }


async def fetch_piece_content(
    campaign_id: str,
    piece_id: str,
    commercial_space: Optional[str] = None,
) -> dict[str, Any]:
    """
    Call GET .../api/campaigns/{campaign_id}/creative-pieces/{piece_id}/content.
    Returns dict with contentType and content (HTML string or base64 data URL).
    """
    s = get_settings()
    url = f"{s.campaigns_service_url}/api/campaigns/{campaign_id}/creative-pieces/{piece_id}/content"
    params = {}
    if commercial_space is not None:
        params["commercial_space"] = commercial_space

    async with httpx.AsyncClient(timeout=s.http_timeout) as client:
        resp = await client.get(url, headers=_service_headers(), params=params or None)
        resp.raise_for_status()
        data = resp.json()

    if "contentType" in data:
        data.setdefault("content_type", data["contentType"])
    return data
