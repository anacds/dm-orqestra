import hashlib
import logging
import os
from typing import Optional

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.agent.nodes import retrieve_node, generate_node
from app.agent.retriever import HybridWeaviateRetriever
from app.agent.cache import CacheManager
from app.core.config import settings
from app.core.models_config import load_models_config

logger = logging.getLogger(__name__)


class LegalAgent:
    """Agent for legal validation using RAG with Weaviate."""

    def __init__(
        self,
        weaviate_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        temperature: float = 0.0,
        redis_url: Optional[str] = None,
        cache_enabled: Optional[bool] = None,
        cache_ttl: Optional[int] = None,
    ):
        self.retriever = HybridWeaviateRetriever(
            weaviate_url=weaviate_url,
            embedding_model=embedding_model,
        )

        config = load_models_config()
        llm_config = config.get("models", {}).get("llm", {})
        channels_config = llm_config.get("channels", {})
        defaults = llm_config.get("defaults", {})
        maritaca_base_url = os.getenv(
            "MARITACA_BASE_URL",
            llm_config.get("maritaca_base_url", "https://chat.maritaca.ai/api"),
        )

        maritaca_api_key = (os.getenv("MARITACA_API_KEY") or "").strip()
        openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()

        llm_temperature = float(defaults.get("temperature", llm_config.get("temperature", temperature)))
        max_tokens = int(defaults.get("max_tokens", llm_config.get("max_tokens", 15000)))
        timeout = int(defaults.get("timeout", llm_config.get("timeout", 20)))
        max_retries = int(defaults.get("max_retries", llm_config.get("max_retries", 2)))

        llm_by_provider: dict[str, object] = {}
        channel_to_llm: dict[str, object] = {}
        default_llm = None

        for ch, cfg in channels_config.items():
            prov = (cfg or {}).get("provider", "maritaca")
            model_name = (cfg or {}).get("model", "sabiazinho-4")
            key = (prov, model_name)
            if key not in llm_by_provider:
                if prov == "maritaca":
                    if not maritaca_api_key:
                        raise ValueError(
                            f"Canal {ch} usa provider=maritaca mas MARITACA_API_KEY não está definida."
                        )
                    llm_by_provider[key] = ChatOpenAI(
                        model=model_name,
                        api_key=maritaca_api_key,
                        base_url=maritaca_base_url,
                        temperature=llm_temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        max_retries=max_retries,
                    )
                elif prov == "openai":
                    if not openai_api_key:
                        raise ValueError(
                            f"Canal {ch} usa provider=openai mas OPENAI_API_KEY não está definida."
                        )
                    llm_by_provider[key] = ChatOpenAI(
                        model=model_name,
                        api_key=openai_api_key,
                        base_url="https://api.openai.com/v1",
                        temperature=llm_temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        max_retries=max_retries,
                    )
                else:
                    raise ValueError(f"Provider não suportado: {prov} (canal {ch})")
            channel_to_llm[ch] = llm_by_provider[key]
            if default_llm is None:
                default_llm = llm_by_provider[key]

        if not channel_to_llm:
            raise ValueError("Nenhum canal configurado em models.llm.channels.")

        self.channel_to_llm = channel_to_llm
        self.default_llm = default_llm
        self.llm = default_llm  # compatibilidade
        self.channel_to_model = {
            ch: (cfg or {}).get("model", "sabiazinho-4")
            for ch, cfg in channels_config.items()
        }

        self.cache = CacheManager(
            redis_url=redis_url or settings.REDIS_URL,
            enabled=cache_enabled if cache_enabled is not None else settings.CACHE_ENABLED,
            ttl=cache_ttl or settings.CACHE_TTL,
        )

        self.graph = self._build_graph()
        self.app = self.graph.compile()

        summary = ", ".join(
            f"{ch}=({cfg.get('provider')},{cfg.get('model')})"
            for ch, cfg in channels_config.items()
        )
        logger.info("Legal agent initialized: llm por canal: %s", summary)

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow for legal validation."""
        workflow = StateGraph(AgentState)

        workflow.add_node("retrieve", lambda state: retrieve_node(state, self.retriever))
        workflow.add_node(
            "generate",
            lambda state: generate_node(
                state,
                self.channel_to_llm,
                self.default_llm,
            ),
        )

        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        
        return workflow
    
    def invoke(self, task: Optional[str] = None,
               channel: Optional[str] = None, 
               content: Optional[str] = None,
               content_title: Optional[str] = None,
               content_body: Optional[str] = None,
               content_image: Optional[str] = None) -> dict:
        """Validate communication and return structured result.
        
        Args:
            task: Validation task type
            channel: Communication channel (e.g., SMS, EMAIL, PUSH, APP)
            content: Content to validate (backward compatibility - string concatenada)
            content_title: Title for PUSH/EMAIL (optional)
            content_body: Body text for SMS, PUSH, EMAIL (optional)
            content_image: For APP, uma data URL (base64, máx. 1 MB). No download.
        
        Returns:
            Dictionary with decision, summary, and sources
        """
        if not task:
            raise ValueError("task é obrigatório")
        
        # --- CÓDIGO LEGADO: apenas APP aceitava content_image ---
        # if channel != "APP":
        #     if not content_body and not content:
        #         raise ValueError("task e content (ou content_body) são obrigatórios")
        #     content_body = content_body or content
        # elif not content_image:
        #     raise ValueError("Para channel=APP, informe content_image")
        # --- FIM CÓDIGO LEGADO ---
        
        # EMAIL agora pode ter content_image (análise visual) ou content_body
        if channel == "APP":
            if not content_image:
                raise ValueError("Para channel=APP, informe content_image")
        elif channel == "EMAIL":
            # EMAIL pode ter image (visual) ou body
            if not content_image and not content_body and not content:
                raise ValueError("Para channel=EMAIL, informe content_image ou content_body")
            if not content_image:
                content_body = content_body or content
        else:
            if not content_body and not content:
                raise ValueError("task e content (ou content_body) são obrigatórios")
            content_body = content_body or content
        
        if not content_body:
            content_body = content

        cache_key_content = content_body or content or ""
        # --- CÓDIGO LEGADO: usava apenas hash de imagem ---
        # if content_image:
        #     cache_key_content = f"{channel}:" + hashlib.sha256(content_image...).hexdigest()[:24]
        # --- FIM CÓDIGO LEGADO ---
        
        # Cache key inclui hash de imagem + texto (para EMAIL com ambos)
        if content_image and content_body:
            combined = f"{content_body}:{content_image}"
            cache_key_content = f"{channel}:" + hashlib.sha256(
                combined.encode("utf-8")
            ).hexdigest()[:32]
        elif content_image:
            cache_key_content = f"{channel}:" + hashlib.sha256(
                content_image.encode("utf-8")
            ).hexdigest()[:24]
        cached_result = self.cache.get(task, channel, cache_key_content)
        if cached_result:
            logger.info(f"Retornando resultado do cache para task={task}, channel={channel}")
            return cached_result
        
        initial_state = {
            "task": task,
            "channel": channel,
            "content": content or content_body or "",
            "content_title": content_title,
            "content_body": content_body,
            "content_image": content_image,
            "retrieved_chunks": [],
            "context": "",
            "sources": [],
            "decision": None,
            "requires_human_review": None,
            "summary": None,
            "iteration_count": 0,
            "max_iterations": 3,
            "search_metadata": None,
        }
        logger.info(f"Invoking agent with structured input: task={task}, channel={channel}")
        
        result = self.app.invoke(initial_state)
        
        formatted_result = {
            "decision": result.get("decision", "REPROVADO"),
            "requires_human_review": result.get("requires_human_review", True),
            "summary": result.get("summary", ""),
            "sources": result.get("sources", []),
        }
        
        formatted_result["_internal"] = {
            "retrieved_chunks": result.get("retrieved_chunks", []),
            "search_metadata": result.get("search_metadata"),
            "num_chunks_retrieved": len(result.get("retrieved_chunks", [])),
        }
        
        self.cache.set(task, channel, cache_key_content, formatted_result)
        
        return formatted_result
    
    def close(self):
        if self.retriever:
            self.retriever.close()
        if self.cache:
            self.cache.close()


# -----------------------------------------------------------------------------
# Compiled graph for LangGraph Studio (langgraph dev).
# Requires: WEAVIATE_URL, OPENAI_API_KEY (and optionally MARITACA_API_KEY, REDIS_URL).
# Input example: {"task": "VALIDATE_COMMUNICATION", "channel": "SMS", "content": "Orqestra: ..."}
# -----------------------------------------------------------------------------
graph = LegalAgent().app

