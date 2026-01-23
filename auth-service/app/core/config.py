from pydantic_settings import BaseSettings
from typing import List
import json
import os


def parse_cors_origins(value: str) -> List[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"CORS_ORIGINS must be a JSON array, got: {type(parsed).__name__}")
    
    if not all(isinstance(item, str) for item in parsed):
        raise ValueError("CORS_ORIGINS array must contain only strings")
    
    return parsed


class Settings(BaseSettings):
    # Infrastructure
    DATABASE_URL: str = "postgresql://orqestra:orqestra_password@localhost:5432/auth_service"
    
    # Credentials (sensitive, from environment)
    SECRET_KEY: str = os.environ.get("SECRET_KEY") 
    
    # Environment
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "auth-service"
    SERVICE_VERSION: str = "1.0.0"
    
    # Auth behavior configuration is loaded from config/auth.yaml
    # See app.core.auth_config.load_auth_config()
    
    @property
    def SECURE_COOKIES(self) -> bool:
        return self.ENVIRONMENT == "production"
    
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

