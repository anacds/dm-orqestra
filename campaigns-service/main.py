from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router
from app.core.config import settings
from app.core.s3_client import ensure_bucket_exists

app = FastAPI(
    title="Orqestra Campaigns Service",
    description="Campaign Management API",
    version=settings.SERVICE_VERSION,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api/campaigns", tags=["campaigns"])

@app.on_event("startup")
async def startup_event():
    try:
        ensure_bucket_exists()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"could not initialize s3 bucket: {e}")

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running"
    }

