import yaml
import json
import os
from pathlib import Path
from typing import List

_config = None

def _load():
    global _config
    if _config is None:
        config_file = Path("config/config.yaml")
        if config_file.exists():
            with open(config_file) as f:
                _config = yaml.safe_load(f) or {}
        else:
            _config = {}
    return _config

def _get(key: str, default):
    return _load().get(key, default)

def _service_url(name: str) -> str:
    env_key = f"{name.upper().replace('-', '_')}_SERVICE_URL"
    return os.getenv(env_key) or _get("services", {}).get(name, {}).get("url", f"http://{name}:8000")

SERVICE_NAME = os.getenv("SERVICE_NAME") or _get("service", {}).get("name", "api-gateway")
SERVICE_VERSION = os.getenv("SERVICE_VERSION") or _get("service", {}).get("version", "1.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT") or _get("service", {}).get("environment", "development")

SECRET_KEY = os.getenv("SECRET_KEY") or _get("auth", {}).get("secret_key")
ALGORITHM = os.getenv("ALGORITHM") or _get("auth", {}).get("algorithm", "HS256")

AUTH_SERVICE_URL = _service_url("auth")
CAMPAIGNS_SERVICE_URL = _service_url("campaigns")
BRIEFING_ENHANCER_SERVICE_URL = _service_url("briefing-enhancer")
CONTENT_SERVICE_URL = _service_url("content")

def get_cors_origins() -> List[str]:
    cors_env = os.getenv("CORS_ORIGINS")
    if cors_env:
        try:
            return json.loads(cors_env)
        except json.JSONDecodeError:
            return [cors_env]
    return _get("cors", {}).get("origins", ["http://localhost:3000"])

