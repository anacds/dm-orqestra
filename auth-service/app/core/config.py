from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # Infrastructure (sempre injetado via docker-compose; vazio = erro explícito se esquecido)
    DATABASE_URL: str = ""

    # Credentials (sensitive, from environment)
    SECRET_KEY: str = ""

    # Environment
    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "auth-service"
    SERVICE_VERSION: str = "1.0.0"

    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Auth behavior configuration is loaded from config/auth.yaml
    # See app.core.auth_config.load_auth_config()

    @property
    def SECURE_COOKIES(self) -> bool:
        return self.ENVIRONMENT == "production"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

if not settings.SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY não definido. Defina via variável de ambiente SECRET_KEY."
    )

