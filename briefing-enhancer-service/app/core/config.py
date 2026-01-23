from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://auth-service:8002"
    
    SERVICE_NAME: str = "briefing-enhancer-service"
    SERVICE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    HOST: str = "0.0.0.0"
    PORT: int = 8001
  
    DATABASE_URL: str = ""
 
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

