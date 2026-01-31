"""Configuration for campaigns-mcp-server."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """Settings loaded from environment."""

    campaigns_service_url: str
    port: int
    service_user_id: str
    service_user_email: str
    service_user_role: str
    service_user_is_active: str
    http_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        base = os.getenv("CAMPAIGNS_SERVICE_URL", "http://campaigns-service:8003").rstrip("/")
        return cls(
            campaigns_service_url=base,
            port=int(os.getenv("PORT", "8010")),
            service_user_id=os.getenv("MCP_SERVICE_USER_ID", "svc-mcp-campaigns"),
            service_user_email=os.getenv("MCP_SERVICE_USER_EMAIL", "mcp-campaigns@internal"),
            service_user_role=os.getenv("MCP_SERVICE_USER_ROLE", "Analista de criação"),
            service_user_is_active=os.getenv("MCP_SERVICE_USER_IS_ACTIVE", "true"),
            http_timeout=float(os.getenv("HTTP_TIMEOUT", "30")),
        )


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
