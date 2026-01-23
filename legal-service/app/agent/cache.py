import json
import hashlib
import logging
from typing import Optional, Dict, Any
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        enabled: bool = True,
        ttl: int = 3600,
    ):
        self.enabled = enabled
        self.ttl = ttl
        self.redis_client = None
        
        if not enabled:
            logger.info("Cache desabilitado")
            return
        
        try:
            redis_url = redis_url or settings.REDIS_URL
            if not redis_url:
                logger.warning("REDIS_URL não configurada, cache desabilitado")
                self.enabled = False
                return
            
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info(f"Cache Redis conectado: {redis_url}")
        except Exception as e:
            logger.warning(f"Erro ao conectar ao Redis: {e}. Cache desabilitado.")
            self.enabled = False
            self.redis_client = None
    
    def _generate_key(self, task: str, channel: Optional[str], content: str) -> str:
        input_data = {
            "task": task,
            "channel": channel,
            "content": content,
        }
        input_str = json.dumps(input_data, sort_keys=True, ensure_ascii=False)
        hash_obj = hashlib.sha256(input_str.encode('utf-8'))
        cache_key = f"legal_agent:{hash_obj.hexdigest()}"
        return cache_key
    
    def get(self, task: str, channel: Optional[str], content: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_key(task, channel, content)
            cached_value = self.redis_client.get(cache_key)
            
            if cached_value:
                result = json.loads(cached_value)
                logger.info(f"Cache HIT para task={task}, channel={channel}")
                return result
            else:
                logger.debug(f"Cache MISS para task={task}, channel={channel}")
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar do cache: {e}", exc_info=True)
            return None
    
    def set(self, task: str, channel: Optional[str], content: str, result: Dict[str, Any]) -> bool:
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_key(task, channel, content)
            result_json = json.dumps(result, ensure_ascii=False)
            self.redis_client.setex(cache_key, self.ttl, result_json)
            logger.info(f"Cache SET para task={task}, channel={channel}, TTL={self.ttl}s")
            return True
        except Exception as e:
            logger.error(f"Erro ao armazenar no cache: {e}", exc_info=True)
            return False
    
    def clear(self) -> bool:
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            keys = self.redis_client.keys("legal_agent:*")
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cache limpo: {len(keys)} chaves removidas")
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}", exc_info=True)
            return False
    
    def close(self):
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Conexão Redis fechada")
            except Exception as e:
                logger.error(f"Erro ao fechar conexão Redis: {e}")

