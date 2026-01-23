import yaml
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

_config_cache: Dict[str, Any] = None

def load_auth_config() -> Dict[str, Any]:
    """
    Load auth configuration from YAML file.
    Caches the configuration for subsequent calls.
    """
    global _config_cache
    if _config_cache is None:
        config_file = Path("config/auth.yaml")
        if config_file.exists():
            try:
                with open(config_file) as f:
                    _config_cache = yaml.safe_load(f) or {}
                logger.info(f"Loaded auth configuration from {config_file}")
            except Exception as e:
                logger.error(f"Error loading auth configuration: {e}")
                _config_cache = {}
        else:
            logger.warning(f"Auth configuration file not found at {config_file}, using defaults")
            _config_cache = {}
    return _config_cache

