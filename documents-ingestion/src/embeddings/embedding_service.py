import logging
import os
from typing import List, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "text-embedding-3-small"


def _parse_timeout() -> float:
    raw = os.getenv("EMBEDDING_REQUEST_TIMEOUT", "60")
    try:
        return max(5.0, float(raw))
    except (TypeError, ValueError):
        return 60.0


class EmbeddingService:
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ):
        self.model = model or DEFAULT_MODEL
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.request_timeout = (
            request_timeout if request_timeout is not None else _parse_timeout()
        )

        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL", "").strip() or None

        client_kwargs = {"api_key": self.api_key, "timeout": self.request_timeout}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url
        self.client = OpenAI(**client_kwargs)

        logger.info(
            "EmbeddingService initialized (model=%s, request_timeout=%ss)",
            self.model,
            self.request_timeout,
        )

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        all_embeddings = []
        num_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_num = i // batch_size + 1

            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.debug(
                    "Generated embeddings for batch %s/%s (%s texts)",
                    batch_num,
                    num_batches,
                    len(batch),
                )

            except Exception as e:
                logger.error(
                    "Error generating embeddings for batch %s/%s (size=%s, timeout=%ss): %s",
                    batch_num,
                    num_batches,
                    len(batch),
                    self.request_timeout,
                    e,
                    exc_info=True,
                )
                raise

        logger.info("Generated %s embeddings total", len(all_embeddings))
        return all_embeddings


def create_embedding_service(
    model: Optional[str] = None,
    request_timeout: Optional[float] = None,
) -> EmbeddingService:
    model = model or os.getenv("EMBEDDING_MODEL")
    if request_timeout is None:
        request_timeout = _parse_timeout()

    return EmbeddingService(
        model=model,
        request_timeout=request_timeout,
    )
