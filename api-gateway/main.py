from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from app.config import SERVICE_VERSION, SERVICE_NAME, get_cors_origins, AUTH_SERVICE_URL, CAMPAIGNS_SERVICE_URL, BRIEFING_ENHANCER_SERVICE_URL, CONTENT_SERVICE_URL, ENVIRONMENT
from app.gateway import proxy_request, get_service_url
from app.rate_limit import limiter, rate_limit_handler, get_rate_limit_for_path
from app.auth import validate_and_extract_user, should_skip_auth
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Orqestra API Gateway",
    version=SERVICE_VERSION,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@limiter.limit(lambda request: get_rate_limit_for_path(request.url.path))
async def gateway(request: Request, path: str):
    if request.method == "OPTIONS":
        return Response(status_code=200)
    
    full_path = f"/api/{path}"

    user_context = None
    if not should_skip_auth(full_path):
        user_context = await validate_and_extract_user(request)
        if not user_context:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    service_url = get_service_url(full_path)
    
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
    
    try:
        response_body, status_code, response_headers = await proxy_request(
            request=request,
            service_url=service_url,
            path=full_path,
            method=request.method,
            body=body,
            user_context=user_context
        )
        
        set_cookie_headers = response_headers.pop("_set_cookie", [])
        
        response = Response(
            content=response_body,
            status_code=status_code,
            headers=response_headers,
            media_type=response_headers.get("content-type", "application/json")
        )
    except Exception as e:
        logger.error(f"Error processing response: {type(e).__name__}: {e}", exc_info=True)
        raise
    
    if set_cookie_headers:
        for cookie_str in set_cookie_headers:
            parts = cookie_str.split(";")
            if not parts:
                continue
            
            name_value = parts[0].strip().split("=", 1)
            if len(name_value) != 2:
                continue
            
            cookie_name = name_value[0].strip()
            cookie_value = name_value[1].strip()
            cookie_kwargs = {}

            for part in parts[1:]:
                part = part.strip()
                if part.lower() == "httponly":
                    cookie_kwargs["httponly"] = True
                elif part.lower().startswith("path="):
                    cookie_kwargs["path"] = part.split("=", 1)[1].strip()
                elif part.lower().startswith("samesite="):
                    samesite_value = part.split("=", 1)[1].strip().lower()
                    cookie_kwargs["samesite"] = samesite_value
                elif part.lower().startswith("max-age="):
                    try:
                        cookie_kwargs["max_age"] = int(part.split("=", 1)[1].strip())
                    except ValueError:
                        pass
                elif part.lower().startswith("secure"):
                    cookie_kwargs["secure"] = ENVIRONMENT == "production"
            
            try:
                response.set_cookie(
                    key=cookie_name,
                    value=cookie_value,
                    **cookie_kwargs
                )
            except Exception:
                response.headers.append("set-cookie", cookie_str)
    
    return response


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
                "services": {
                    "auth": AUTH_SERVICE_URL,
                    "campaigns": CAMPAIGNS_SERVICE_URL,
                    "briefing-enhancer": BRIEFING_ENHANCER_SERVICE_URL,
                    "content": CONTENT_SERVICE_URL,
                }
    }


@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "running"
    }

