from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from app.core.auth_config import load_auth_config

limiter = Limiter(key_func=get_remote_address)

def get_login_rate_limit():
    config = load_auth_config()
    rate_limit_config = config.get("auth", {}).get("rate_limit", {})
    enabled = rate_limit_config.get("enabled", True)
    if enabled:
        per_minute = rate_limit_config.get("login_per_minute", 50)
        return f"{per_minute}/minute"
    return "1000/minute"

def get_register_rate_limit():
    config = load_auth_config()
    rate_limit_config = config.get("auth", {}).get("rate_limit", {})
    enabled = rate_limit_config.get("enabled", True)
    if enabled:
        per_hour = rate_limit_config.get("register_per_hour", 300)
        return f"{per_hour}/hour"
    return "1000/hour"

rate_limit_handler = _rate_limit_exceeded_handler

