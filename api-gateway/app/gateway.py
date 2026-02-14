import time

import httpx
from fastapi import Request, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import Optional
from app.config import AUTH_SERVICE_URL, CAMPAIGNS_SERVICE_URL, BRIEFING_ENHANCER_SERVICE_URL, CONTENT_VALIDATION_SERVICE_URL
from app.auth import validate_and_extract_user, should_skip_auth
from app.metrics import PROXY_REQUESTS, PROXY_DURATION, UPSTREAM_ERRORS
import logging

logger = logging.getLogger(__name__)


async def proxy_request(
    request: Request,
    service_url: str,
    path: str,
    method: str = "GET",
    body: Optional[bytes] = None,
    headers: Optional[dict] = None,
    user_context: Optional[dict] = None
) -> tuple[bytes, int, dict]:
    """Proxy HTTP request to downstream service with user context headers."""
    url = f"{service_url}{path}"
    
    proxy_headers = {}
    if headers:
        proxy_headers.update(headers)
    
    if user_context:
        import base64
        
        def to_ascii_safe(value: str) -> str:
            """Encode non-ASCII header values as base64."""
            if not value:
                return ""
            try:
                value.encode('ascii')
                return value
            except UnicodeEncodeError:
                encoded = base64.b64encode(value.encode('utf-8')).decode('ascii')
                return f"base64:{encoded}"
        
        user_id = user_context.get("id", "")
        user_email = user_context.get("email", "")
        user_role = user_context.get("role", "")
        user_is_active = str(user_context.get("is_active", False))
        
        proxy_headers["X-User-Id"] = to_ascii_safe(str(user_id))
        proxy_headers["X-User-Email"] = to_ascii_safe(str(user_email))
        proxy_headers["X-User-Role"] = to_ascii_safe(str(user_role))
        proxy_headers["X-User-Is-Active"] = user_is_active
    
    auth_header = request.headers.get("authorization")
    if auth_header:
        proxy_headers["authorization"] = auth_header
    
    content_type = request.headers.get("content-type")
    if content_type:
        proxy_headers["content-type"] = content_type
    
    cookie_header = request.headers.get("cookie")
    if cookie_header:
        proxy_headers["cookie"] = cookie_header
    
    target_service = _resolve_target_name(service_url)
    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            if method == "GET":
                response = await client.get(url, headers=proxy_headers, params=request.query_params)
            elif method == "POST":
                response = await client.post(url, headers=proxy_headers, content=body, params=request.query_params)
            elif method == "PUT":
                response = await client.put(url, headers=proxy_headers, content=body, params=request.query_params)
            elif method == "PATCH":
                response = await client.patch(url, headers=proxy_headers, content=body, params=request.query_params)
            elif method == "DELETE":
                response = await client.delete(url, headers=proxy_headers, params=request.query_params)
            else:
                raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Method not allowed")
            
            elapsed = time.perf_counter() - start
            PROXY_DURATION.labels(target_service=target_service, method=method).observe(elapsed)
            PROXY_REQUESTS.labels(target_service=target_service, method=method, status_code=str(response.status_code)).inc()

            response_body = response.content
            response_headers = dict(response.headers)
            hop_by_hop = ["connection", "keep-alive", "transfer-encoding", "upgrade"]
            for header in hop_by_hop:
                response_headers.pop(header, None)
            
            set_cookie_headers_raw = response.headers.get_list("set-cookie")
            if not set_cookie_headers_raw:
                set_cookie_headers = [
                    value for name, value in response.headers.items()
                    if name.lower() == "set-cookie"
                ]
            else:
                set_cookie_headers = set_cookie_headers_raw
            
            if set_cookie_headers:
                response_headers["_set_cookie"] = set_cookie_headers
            
            return response_body, response.status_code, response_headers
            
    except httpx.TimeoutException:
        UPSTREAM_ERRORS.labels(target_service=target_service, error_type="timeout").inc()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Service timeout"
        )
    except httpx.ConnectError:
        UPSTREAM_ERRORS.labels(target_service=target_service, error_type="connection").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        UPSTREAM_ERRORS.labels(target_service=target_service, error_type="other").inc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gateway error: {str(e)}"
        )


async def proxy_request_stream(
    request: Request,
    service_url: str,
    path: str,
    body: Optional[bytes] = None,
    user_context: Optional[dict] = None,
) -> StreamingResponse:
    """Proxy SSE streaming request to downstream service."""
    url = f"{service_url}{path}"

    proxy_headers: dict[str, str] = {}
    if user_context:
        import base64

        def to_ascii_safe(value: str) -> str:
            if not value:
                return ""
            try:
                value.encode("ascii")
                return value
            except UnicodeEncodeError:
                encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
                return f"base64:{encoded}"

        proxy_headers["X-User-Id"] = to_ascii_safe(str(user_context.get("id", "")))
        proxy_headers["X-User-Email"] = to_ascii_safe(str(user_context.get("email", "")))
        proxy_headers["X-User-Role"] = to_ascii_safe(str(user_context.get("role", "")))
        proxy_headers["X-User-Is-Active"] = str(user_context.get("is_active", False))

    auth_header = request.headers.get("authorization")
    if auth_header:
        proxy_headers["authorization"] = auth_header
    proxy_headers["content-type"] = "application/json"

    target_service = _resolve_target_name(service_url)

    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream(
                    "POST", url, headers=proxy_headers, content=body
                ) as response:
                    PROXY_REQUESTS.labels(
                        target_service=target_service,
                        method="POST",
                        status_code=str(response.status_code),
                    ).inc()
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except httpx.TimeoutException:
            UPSTREAM_ERRORS.labels(target_service=target_service, error_type="timeout").inc()
            yield b"event: error\ndata: {\"error\": \"Service timeout\"}\n\n"
        except httpx.ConnectError:
            UPSTREAM_ERRORS.labels(target_service=target_service, error_type="connection").inc()
            yield b"event: error\ndata: {\"error\": \"Service unavailable\"}\n\n"
        except Exception as e:
            UPSTREAM_ERRORS.labels(target_service=target_service, error_type="other").inc()
            yield f"event: error\ndata: {{\"error\": \"{e}\"}}\n\n".encode()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_SERVICE_URL_NAMES = {
    AUTH_SERVICE_URL: "auth",
    CAMPAIGNS_SERVICE_URL: "campaigns",
    BRIEFING_ENHANCER_SERVICE_URL: "briefing-enhancer",
    CONTENT_VALIDATION_SERVICE_URL: "content-validation",
}


def _resolve_target_name(service_url: str) -> str:
    """Resolve human-readable service name from URL."""
    return _SERVICE_URL_NAMES.get(service_url, "unknown")


def get_service_url(path: str) -> str:
    """Determine downstream service URL based on request path."""
    if path.startswith("/api/auth"):
        return AUTH_SERVICE_URL
    elif path.startswith("/api/campaigns"):
        return CAMPAIGNS_SERVICE_URL
    elif path.startswith("/api/ai/analyze-piece") or path.startswith("/api/ai/generate-text"):
        return CONTENT_VALIDATION_SERVICE_URL
    elif path.startswith("/api/ai-interactions") or path.startswith("/api/ai") or path.startswith("/api/enhance-objective"):
        return BRIEFING_ENHANCER_SERVICE_URL
    else:
        return CAMPAIGNS_SERVICE_URL


def strip_api_prefix(path: str) -> str:
    """Remove /api prefix from path for downstream services."""
    if path.startswith("/api/"):
        return path[4:] 
    elif path.startswith("/api"):
        return path[4:]  
    return path

