import logging
import os
from typing import List, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.model = model or self._get_default_model()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        env_base_url = os.getenv("OPENAI_BASE_URL", "")
        if env_base_url:
            env_base_url = env_base_url.strip()
        
        final_base_url = base_url if base_url else (env_base_url if env_base_url else None)
        if final_base_url:
            final_base_url = final_base_url.strip()
            if not final_base_url:
                final_base_url = None
        
        self.base_url = final_base_url

        if self.provider == "openai":
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self.client = OpenAI(**client_kwargs)
        elif self.provider in ["ollama", "local"]:
            if not self.base_url:
                self.base_url = "http://localhost:11434"
            self.client = OpenAI(api_key="ollama", base_url=self.base_url)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def _get_default_model(self) -> str:
        defaults = {
            "openai": "text-embedding-3-small",
            "ollama": "nomic-embed-text",
            "local": "nomic-embed-text",
        }
        return defaults.get(self.provider, "text-embedding-3-small")

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            try:
                if self.provider in ["openai", "ollama", "local"]:
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=batch,
                    )
                    batch_embeddings = [item.embedding for item in response.data]
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")

                all_embeddings.extend(batch_embeddings)

                logger.debug(
                    f"Generated embeddings for batch {i//batch_size + 1} "
                    f"({len(batch)} texts)"
                )

            except Exception as e:
                logger.error(f"Error generating embeddings for batch: {e}")
                raise

        logger.info(f"Generated {len(all_embeddings)} embeddings total")
        return all_embeddings


def create_embedding_service(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> EmbeddingService:
    provider = provider or os.getenv("EMBEDDING_PROVIDER", "openai")
    model = model or os.getenv("EMBEDDING_MODEL")

    return EmbeddingService(provider=provider, model=model)

