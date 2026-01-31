from __future__ import annotations

import json
import os
from typing import List

from pydantic_settings import BaseSettings


def parse_cors_origins(value: str) -> List[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
        raise ValueError("CORS_ORIGINS must be a JSON array of strings")
    return parsed


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "content-validation-service"
    SERVICE_VERSION: str = "1.0.0"
    AUTH_SERVICE_URL: str = "http://auth-service:8002"
    LEGAL_SERVICE_URL: str = "http://legal-service:8005"
    CAMPAIGNS_MCP_URL: str = "http://campaigns-mcp-server:8010"
    HTML_CONVERTER_MCP_URL: str = "http://html-converter-service:8011"
    HTTP_TIMEOUT: float = 30.0
    A2A_BASE_URL: str = "http://localhost:8004"
    DATABASE_URL: str = "postgresql://orqestra:orqestra_password@localhost:5432/content_validation"
    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def CORS_ORIGINS(self) -> List[str]:
        raw = os.getenv("CORS_ORIGINS")
        if not raw:
            return ["http://localhost:3000"]
        return parse_cors_origins(raw)


settings = Settings()
