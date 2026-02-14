from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    SERVICE_NAME: str = "legal-service"
    SERVICE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8005
    DATABASE_URL: str = ""
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    WEAVIATE_URL: str = "http://weaviate:8080"
    REDIS_URL: str = "redis://redis:6379/0"
    A2A_BASE_URL: str = "http://localhost:8005"
    WEAVIATE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    WEAVIATE_CLASS_NAME: str = "LegalDocuments"
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

