import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    port: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            port=int(os.getenv("PORT", "8012")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
