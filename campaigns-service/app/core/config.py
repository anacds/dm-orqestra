from pydantic_settings import BaseSettings
from typing import List
import json
import os


def parse_cors_origins(value: str) -> List[str]:
    """Parse CORS_ORIGINS from JSON array string"""
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"CORS_ORIGINS must be a JSON array, got: {type(parsed).__name__}")
    
    if not all(isinstance(item, str) for item in parsed):
        raise ValueError("CORS_ORIGINS array must contain only strings")
    
    return parsed


class Settings(BaseSettings):

    DATABASE_URL: str = "postgresql://orqestra:orqestra_password@localhost:5432/campaigns_service"
    AUTH_SERVICE_URL: str = "http://auth-service:8002"
    
    AWS_ACCESS_KEY_ID: str = "test"
    AWS_SECRET_ACCESS_KEY: str = "test"
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = "http://localstack:4566"
    S3_PUBLIC_URL: str = "http://localhost:4566"
    S3_BUCKET_NAME: str = "orqestra-creative-pieces"
    
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "campaigns-service"
    SERVICE_VERSION: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        raw_value = os.getenv("CORS_ORIGINS")
        if not raw_value:
            return ["http://localhost:3000"]
        return parse_cors_origins(raw_value)


settings = Settings()

