from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "content-validation-service"
    SERVICE_VERSION: str = "1.0.0"
    AUTH_SERVICE_URL: str = "http://auth-service:8002"
    LEGAL_SERVICE_URL: str = "http://legal-service:8005"
    CAMPAIGNS_MCP_URL: str = "http://campaigns-service:8003"
    HTML_CONVERTER_MCP_URL: str = "http://html-converter-service:8011"
    BRANDING_MCP_URL: str = "http://branding-service:8012"
    HTTP_TIMEOUT: float = 120.0
    A2A_TIMEOUT: float = 300.0  # timeout para chamadas A2A (legal-service: RAG + rerank + LLM)
    A2A_BASE_URL: str = "http://localhost:8004"
    # Infrastructure (sempre injetado via docker-compose; vazio = erro explícito se esquecido)
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://redis:6379/1"
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 86400  # 24h in seconds

    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
