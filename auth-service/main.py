from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.routes import router
from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_handler
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="Orqestra Auth Service",
    description="Authentication and User Management API",
    version=settings.SERVICE_VERSION,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/auth", tags=["auth"])

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/health", "/api/health"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}

@app.get("/")
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running"
    }

