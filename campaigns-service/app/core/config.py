from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):

    # Infrastructure (sempre injetado via docker-compose; vazio = erro explícito se esquecido)
    DATABASE_URL: str = ""
    AUTH_SERVICE_URL: str = "http://auth-service:8002"

    # AWS / S3 (injetado via docker-compose; defaults vazios para não expor credenciais)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = "http://localstack:4566"
    S3_PUBLIC_URL: str = "http://localhost:4566"
    S3_BUCKET_NAME: str = "orqestra-creative-pieces"

    ENVIRONMENT: str = "development"
    SERVICE_NAME: str = "campaigns-service"
    SERVICE_VERSION: str = "1.0.0"

    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

