from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Service metadata
    SERVICE_NAME: str = "legal-service"
    SERVICE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    
    # Infrastructure
    HOST: str = "0.0.0.0"
    PORT: int = 8005
    DATABASE_URL: str = ""
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # External services (URLs that may vary between environments)
    WEAVIATE_URL: str = "http://weaviate:8080"
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Credentials (sensitive, from environment)
    WEAVIATE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
    # Infrastructure configuration
    WEAVIATE_CLASS_NAME: str = "DocumentChunk"
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Model configurations are loaded from config/models.yaml
    # See app.core.models_config.load_models_config()
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

