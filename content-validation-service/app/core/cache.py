"""Redis cache for piece validation results."""

import json
import hashlib
import logging
from typing import Optional, Dict, Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


def _content_hash_sms(body: str | None) -> str:
    s = f"SMS:{body or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _content_hash_push(title: str | None, body: str | None) -> str:
    s = f"PUSH:{title or ''}:{body or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _content_hash_email(real_content_hash: str) -> str:
    s = f"EMAIL:{real_content_hash or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _content_hash_app(real_content_hash: str, commercial_space: str) -> str:
    s = f"APP:{real_content_hash or ''}:{commercial_space or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ValidationCacheManager:
    """Redis cache for content-validation results.

    Key format: ``piece_validation:{campaign_id}:{channel}:{content_hash}``
    Also maintains a "latest" pointer per campaign+channel for the GET endpoint.
    """

    PREFIX = "piece_validation"
    LATEST_PREFIX = "piece_validation_latest"

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
            logger.info("Cache desabilitado")
            return

        try:
            url = redis_url or settings.REDIS_URL
            if not url:
                logger.warning("REDIS_URL não configurada, cache desabilitado")
                self.enabled = False
                return

            self.redis_client = redis.from_url(url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Cache Redis conectado: %s", url)
        except Exception as e:
            logger.warning("Erro ao conectar ao Redis: %s. Cache desabilitado.", e)
            self.enabled = False
            self.redis_client = None

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def compute_content_hash(
        channel: str,
        content: dict,
        retrieved_content_hash: str | None = None,
    ) -> str | None:
        """Compute the content hash for a given channel + content dict."""
        ch = channel.upper()
        if ch == "SMS":
            body = content.get("body") if isinstance(content.get("body"), str) else None
            return _content_hash_sms(body)
        elif ch == "PUSH":
            title = content.get("title") if isinstance(content.get("title"), str) else None
            body = content.get("body") if isinstance(content.get("body"), str) else None
            return _content_hash_push(title, body)
        elif ch == "EMAIL":
            if retrieved_content_hash:
                return _content_hash_email(retrieved_content_hash)
            return None
        elif ch == "APP":
            space = content.get("commercial_space") or content.get("commercialSpace")
            if retrieved_content_hash and space:
                return _content_hash_app(retrieved_content_hash, str(space))
            return None
        return None

    def _key(self, campaign_id: str, channel: str, content_hash: str) -> str:
        return f"{self.PREFIX}:{campaign_id}:{channel}:{content_hash}"

    def _latest_key(self, campaign_id: str, channel: str) -> str:
        return f"{self.LATEST_PREFIX}:{campaign_id}:{channel}"

    # ── public API ────────────────────────────────────────────────────

    def get(self, campaign_id: str, channel: str, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached validation by exact content hash."""
        if not self.enabled or not self.redis_client:
            return None
        try:
            raw = self.redis_client.get(self._key(campaign_id, channel, content_hash))
            if raw:
                logger.info("Cache HIT campaign_id=%s channel=%s", campaign_id, channel)
                return json.loads(raw)
            logger.debug("Cache MISS campaign_id=%s channel=%s", campaign_id, channel)
            return None
        except Exception as e:
            logger.error("Erro ao buscar do cache: %s", e)
            return None

    def get_latest(self, campaign_id: str, channel: str) -> Optional[Dict[str, Any]]:
        """Get the most recent cached validation for campaign+channel (used by GET endpoint)."""
        if not self.enabled or not self.redis_client:
            return None
        try:
            raw = self.redis_client.get(self._latest_key(campaign_id, channel))
            if raw:
                logger.info("Cache LATEST HIT campaign_id=%s channel=%s", campaign_id, channel)
                return json.loads(raw)
            return None
        except Exception as e:
            logger.error("Erro ao buscar latest do cache: %s", e)
            return None

    def set(
        self,
        campaign_id: str,
        channel: str,
        content_hash: str,
        result: Dict[str, Any],
    ) -> bool:
        """Cache a validation result and update the latest pointer."""
        if not self.enabled or not self.redis_client:
            return False
        try:
            payload = json.dumps(result, ensure_ascii=False)
            pipe = self.redis_client.pipeline()
            pipe.setex(self._key(campaign_id, channel, content_hash), self.ttl, payload)
            pipe.setex(self._latest_key(campaign_id, channel), self.ttl, payload)
            pipe.execute()
            logger.info(
                "Cache SET campaign_id=%s channel=%s hash=%s TTL=%ds",
                campaign_id, channel, content_hash[:16], self.ttl,
            )
            return True
        except Exception as e:
            logger.error("Erro ao armazenar no cache: %s", e)
            return False

    def close(self):
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Conexão Redis fechada")
            except Exception as e:
                logger.error("Erro ao fechar conexão Redis: %s", e)
