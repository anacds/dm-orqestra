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

        maritaca_api_key = (os.getenv("MARITACA_API_KEY") or "").strip()
        openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()

        llm_temperature = float(llm_config.get("temperature", temperature))
        max_tokens = int(llm_config.get("max_tokens", 15000))
        timeout = int(llm_config.get("timeout", 20))
        max_retries = int(llm_config.get("max_retries", 2))

        if maritaca_api_key:
            provider = "maritaca"
            model_name = llm_config.get("name", "sabiazinho-4")
            base_url = os.getenv("MARITACA_BASE_URL", llm_config.get("base_url", "https://chat.maritaca.ai/api"))
            api_key = maritaca_api_key
        else:
            provider = "openai"
            if not openai_api_key:
                raise ValueError("No MARITACA_API_KEY or OPENAI_API_KEY set in environment")
            model_name = llm_config.get("fallback_model_name", "gpt-5-nano")
            base_url = "https://api.openai.com/v1"
            api_key = openai_api_key

        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=llm_temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )

        self.model_name = model_name
        self.provider = provider

        self.cache = CacheManager(
            redis_url=redis_url or settings.REDIS_URL,
            enabled=cache_enabled if cache_enabled is not None else settings.CACHE_ENABLED,
            ttl=cache_ttl or settings.CACHE_TTL,
        )

        self.graph = self._build_graph()
        self.app = self.graph.compile()

        logger.info(
            "Legal agent initialized with provider=%s, model=%s, base_url=%s",
            provider,
            model_name,
            base_url,
        )

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow for legal validation."""
        workflow = StateGraph(AgentState)

        workflow.add_node("retrieve", lambda state: retrieve_node(state, self.retriever))
        workflow.add_node("generate", lambda state: generate_node(state, self.llm))

        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        
        return workflow
    
    def invoke(self, task: Optional[str] = None,
               channel: Optional[str] = None, 
               content: Optional[str] = None,
               content_title: Optional[str] = None,
               content_body: Optional[str] = None) -> dict:
        """Validate communication and return structured result.
        
        Args:
            task: Validation task type
            channel: Communication channel (e.g., SMS, EMAIL, PUSH)
            content: Content to validate (backward compatibility - string concatenada)
            content_title: Title for PUSH notifications (optional)
            content_body: Body text for SMS or PUSH (optional)
        
        Returns:
            Dictionary with decision, severity, summary, and sources
        """
        # Se content_body não foi fornecido, usa content (backward compatibility)
        if not content_body:
            if not content:
                raise ValueError("task e content (ou content_body) são obrigatórios")
            content_body = content
        
        if not task:
            raise ValueError("task é obrigatório")
        
        # Para cache, usa content_body (ou content se não tiver body)
        cache_key_content = content_body or content
        cached_result = self.cache.get(task, channel, cache_key_content)
        if cached_result:
            logger.info(f"Retornando resultado do cache para task={task}, channel={channel}")
            return cached_result
        
        initial_state = {
            "task": task,
            "channel": channel,
            "content": content or content_body,  # Backward compatibility
            "content_title": content_title,
            "content_body": content_body,
            "retrieved_chunks": [],
            "context": "",
            "sources": [],
            "decision": None,
            "severity": None,
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
            "severity": result.get("severity", "BLOCKER"),
            "requires_human_review": result.get("requires_human_review", True),
            "summary": result.get("summary", ""),
            "sources": result.get("sources", []),
        }
        
        formatted_result["_internal"] = {
            "retrieved_chunks": result.get("retrieved_chunks", []),
            "search_metadata": result.get("search_metadata"),
            "num_chunks_retrieved": len(result.get("retrieved_chunks", [])),
        }
        
        self.cache.set(task, channel, content, formatted_result)
        
        return formatted_result
    
    def stream(self, task: Optional[str] = None, channel: Optional[str] = None, 
               content: Optional[str] = None):
        """Stream validation results as they are generated."""
        if not task or not content:
            raise ValueError("task e content são obrigatórios")
        
        initial_state = {
            "task": task,
            "channel": channel,
            "content": content,
            "retrieved_chunks": [],
            "context": "",
            "sources": [],
            "decision": None,
            "severity": None,
            "requires_human_review": None,
            "summary": None,
            "iteration_count": 0,
            "max_iterations": 3,
            "search_metadata": None,
        }
        
        for state in self.app.stream(initial_state):
            yield state
    
    def close(self):
        if self.retriever:
            self.retriever.close()
        if self.cache:
            self.cache.close()

