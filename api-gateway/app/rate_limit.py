from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
import yaml
from pathlib import Path

_rate_limit_config = None

def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

def load_rate_limit_config():
    global _rate_limit_config
    if _rate_limit_config is None:
        config_file = Path("config/rate_limits.yaml")
        if config_file.exists():
            with open(config_file) as f:
                _rate_limit_config = yaml.safe_load(f) or {}
        else:
            _rate_limit_config = {"enabled": False}
    return _rate_limit_config

config = load_rate_limit_config()
limiter = Limiter(key_func=get_client_ip, enabled=config.get("enabled", True))
rate_limit_handler = _rate_limit_exceeded_handler

def get_rate_limit_for_path(path: str) -> str:
    config = load_rate_limit_config()
    if not config.get("enabled", False):
        return "1000/minute"
    
    normalized_path = path if path.startswith("/api") else f"/api{path}"
    
    paths = config.get("paths", {})
    if normalized_path in paths:
        limit = paths[normalized_path]
        if "requests_per_minute" in limit:
            return f"{limit['requests_per_minute']}/minute"
        if "requests_per_hour" in limit:
            return f"{limit['requests_per_hour']}/hour"
    
    services = config.get("services", {})
    if normalized_path.startswith("/api/auth"):
        service_limit = services.get("auth", {}).get("requests_per_minute", 60)
        return f"{service_limit}/minute"
    elif normalized_path.startswith("/api/campaigns"):
        service_limit = services.get("campaigns", {}).get("requests_per_minute", 80)
        return f"{service_limit}/minute"
    elif normalized_path.startswith("/api/enhance-objective") or normalized_path.startswith("/api/ai-interactions"):
        service_limit = services.get("briefing-enhancer", {}).get("requests_per_minute", 30)
        return f"{service_limit}/minute"
    elif normalized_path.startswith("/api/ai/analyze-piece") or normalized_path.startswith("/api/ai/generate-text"):
        service_limit = services.get("content", {}).get("requests_per_minute", 30)
        return f"{service_limit}/minute"
    
    default = config.get("default", {}).get("requests_per_minute", 100)
    return f"{default}/minute"

