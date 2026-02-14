import atexit
import hashlib
import logging
import os
import time
from typing import Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from app.agent.state import AgentState
from app.agent.nodes import retrieve_node, generate_node
from app.agent.retriever import HybridWeaviateRetriever
from app.agent.cache import CacheManager
from app.core.config import settings
from app.core.models_config import load_models_config
from app.core.metrics import (
    AGENT_INVOCATIONS,
    AGENT_DURATION,
    AGENT_ERRORS,
    SERVICE_INFO,
)

logger = logging.getLogger(__name__)


class LegalAgent:

    def __init__(
        self,
        weaviate_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        temperature: float = 0.0,
        redis_url: Optional[str] = None,
        cache_enabled: Optional[bool] = None,
        cache_ttl: Optional[int] = None,
        alpha_override: Optional[float] = None,
        collection_override: Optional[str] = None,
        rerank_override: Optional[bool] = None,
    ):
        self.alpha_override = alpha_override
        self.collection_override = collection_override
        self.rerank_override = rerank_override
        
        self.retriever = HybridWeaviateRetriever(
            weaviate_url=weaviate_url,
            embedding_model=embedding_model,
            class_name=collection_override,  # Usa collection override se fornecido
            alpha_override=alpha_override,
            rerank_override=rerank_override,
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

        def _is_reasoning_model(name: str) -> bool:
            """Detecta modelos de raciocínio"""
            _lower = name.lower()
            return any(tag in _lower for tag in ("gpt-5", "o1", "o3", "o4"))

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
                    if _is_reasoning_model(model_name):
                        llm_by_provider[key] = ChatOpenAI(
                            model=model_name,
                            api_key=openai_api_key,
                            base_url="https://api.openai.com/v1",
                            timeout=timeout,
                            max_retries=max_retries,
                            model_kwargs={"max_completion_tokens": max(max_tokens, 16000)},
                        )
                        logger.info(
                            f"Canal {ch}: modelo de raciocínio '{model_name}' "
                            f"com max_completion_tokens={max(max_tokens, 16000)}"
                        )
                    else:
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

        SERVICE_INFO.info({
            "version": settings.SERVICE_VERSION,
            "cache_enabled": str(settings.CACHE_ENABLED),
        })
        
        if alpha_override is not None:
            alpha_desc = "BM25 only" if alpha_override == 0.0 else ("Semantic only" if alpha_override == 1.0 else f"Hybrid")
            logger.info(f"[EXPERIMENT] Alpha override: {alpha_override} ({alpha_desc})")
        if collection_override:
            logger.info(f"[EXPERIMENT] Collection override: {collection_override}")
        if rerank_override is not None:
            logger.info(f"[EXPERIMENT] Rerank override: {rerank_override}")

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
        
        if channel == "APP":
            if not content_image:
                raise ValueError("Para channel=APP, informe content_image")
        elif channel == "EMAIL":
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

        cache_parts = [channel or ""]
        if content_title:
            cache_parts.append(content_title)
        if content_body:
            cache_parts.append(content_body)
        elif content:
            cache_parts.append(content)
        if content_image:
            cache_parts.append(hashlib.sha256(content_image.encode("utf-8")).hexdigest()[:24])
        cache_key_content = ":".join(cache_parts)
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
        
        ch_label = channel or "unknown"
        langsmith_config = {
            "metadata": {
                "channel": ch_label,
                "task": task,
            },
            "tags": [ch_label, task],
        }
        start = time.perf_counter()
        try:
            result = self.app.invoke(initial_state, config=langsmith_config)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            AGENT_DURATION.labels(channel=ch_label).observe(elapsed)
            error_type = "timeout" if "timeout" in str(exc).lower() else "unknown"
            AGENT_ERRORS.labels(channel=ch_label, error_type=error_type).inc()
            raise
        
        elapsed = time.perf_counter() - start
        decision = result.get("decision", "REPROVADO")
        
        AGENT_DURATION.labels(channel=ch_label).observe(elapsed)
        AGENT_INVOCATIONS.labels(channel=ch_label, decision=decision).inc()
        
        formatted_result = {
            "decision": decision,
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


_global_agent = None

def get_graph():
    global _global_agent
    if _global_agent is None:
        _global_agent = LegalAgent()
    return _global_agent.app


def _cleanup_global_agent():
    global _global_agent
    if _global_agent is not None:
        try:
            _global_agent.close()
            logger.debug("Global agent closed successfully")
        except Exception as e:
            logger.warning(f"Error closing global agent: {e}")

atexit.register(_cleanup_global_agent)

def __getattr__(name):
    if name == "graph":
        return get_graph()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

