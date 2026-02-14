"""Redis cache for briefing enhancement results."""

import json
import hashlib
import logging
from typing import Optional, Dict, Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class EnhancementCacheManager:
    """Redis cache for briefing enhancement results.

    Key format: ``briefing_cache:{user_id}:{field_name}:{hash(input_text)}:{scope}``
    where scope = ``campaign_{id}`` or ``session_{id}``.
    """

    PREFIX = "briefing_cache"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        enabled: bool = True,
        ttl: int = 86400,  # 24h default
    ):
        self.enabled = enabled
        self.ttl = ttl
        self.redis_client: Optional[redis.Redis] = None

        if not enabled:
            logger.info("Enhancement cache desabilitado")
            return

        try:
            url = redis_url or settings.REDIS_URL
            if not url:
                logger.warning("REDIS_URL não configurada, cache desabilitado")
                self.enabled = False
                return

            self.redis_client = redis.from_url(url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Enhancement cache Redis conectado: %s", url)
        except Exception as e:
            logger.warning("Erro ao conectar ao Redis: %s. Cache desabilitado.", e)
            self.enabled = False
            self.redis_client = None


    @staticmethod
    def _text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _key(
        self,
        user_id: str,
        field_name: str,
        input_text: str,
        campaign_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        text_hash = self._text_hash(input_text)
        scope = f"session_{session_id}" if session_id else f"campaign_{campaign_id}" if campaign_id else "global"
        return f"{self.PREFIX}:{user_id}:{field_name}:{text_hash}:{scope}"

    def get(
        self,
        user_id: str,
        field_name: str,
        input_text: str,
        campaign_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get cached enhancement result."""
        if not self.enabled or not self.redis_client:
            return None
        try:
            key = self._key(user_id, field_name, input_text, campaign_id, session_id)
            raw = self.redis_client.get(key)
            if raw:
                logger.info(
                    "Enhancement cache HIT user=%s field=%s", user_id, field_name,
                )
                return json.loads(raw)
            logger.debug(
                "Enhancement cache MISS user=%s field=%s", user_id, field_name,
            )
            return None
        except Exception as e:
            logger.error("Erro ao buscar do cache de enhancement: %s", e)
            return None

    def set(
        self,
        user_id: str,
        field_name: str,
        input_text: str,
        result: Dict[str, Any],
        campaign_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """Cache an enhancement result."""
        if not self.enabled or not self.redis_client:
            return False
        try:
            key = self._key(user_id, field_name, input_text, campaign_id, session_id)
            payload = json.dumps(result, ensure_ascii=False)
            self.redis_client.setex(key, self.ttl, payload)
            logger.info(
                "Enhancement cache SET user=%s field=%s TTL=%ds",
                user_id, field_name, self.ttl,
            )
            return True
        except Exception as e:
            logger.error("Erro ao armazenar no cache de enhancement: %s", e)
            return False

    def invalidate(
        self,
        user_id: str,
        field_name: str,
        input_text: str,
        campaign_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """Invalidate cache entry (e.g. when user rejects an enhancement)."""
        if not self.enabled or not self.redis_client:
            return False
        try:
            key = self._key(user_id, field_name, input_text, campaign_id, session_id)
            self.redis_client.delete(key)
            logger.info(
                "Enhancement cache INVALIDATED user=%s field=%s", user_id, field_name,
            )
            return True
        except Exception as e:
            logger.error("Erro ao invalidar cache de enhancement: %s", e)
            return False

    def close(self):
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Conexão Redis fechada")
            except Exception as e:
                logger.error("Erro ao fechar conexão Redis: %s", e)
