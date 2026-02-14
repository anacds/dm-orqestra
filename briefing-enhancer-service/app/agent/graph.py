from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from langchain_openai.middleware import OpenAIModerationMiddleware
from langchain.agents import create_agent
from app.agent.state import EnhancementGraphState
from app.agent.nodes import fetch_field_info, enhance_text
from app.core.checkpointer import get_checkpoint_saver
from app.agent.schemas import EnhancedTextResponse
from langsmith import traceable
from app.core.metrics import ENHANCEMENT_TOTAL, ENHANCEMENT_DURATION, LLM_INVOCATIONS
import logging
import os
import time
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

_config_cache = None

def _load_models_config():
    """Load models configuration from YAML. Caches result for subsequent calls."""
    global _config_cache
    if _config_cache is None:
        config_file = Path("config/models.yaml")
        if config_file.exists():
            with open(config_file) as f:
                _config_cache = yaml.safe_load(f) or {}
        else:
            _config_cache = {}
    return _config_cache

@traceable
def create_enhancement_graph(db: Session, structured_llm, checkpointer=None):
    """Create LangGraph workflow for text enhancement.
    
    Args:
        db: Database session
        structured_llm: LangChain agent configured with Maritaca AI
        checkpointer: Optional checkpointer for state persistence
    
    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(EnhancementGraphState)
    
    def fetch_node(state: EnhancementGraphState):
        return fetch_field_info(state, db)
    
    def enhance_node(state: EnhancementGraphState):
        return enhance_text(state, structured_llm)
    
    workflow.add_node("fetch_field_info", fetch_node)
    workflow.add_node("enhance_text", enhance_node)
    
    workflow.set_entry_point("fetch_field_info")
    workflow.add_edge("fetch_field_info", "enhance_text")
    workflow.add_edge("enhance_text", END)

    if checkpointer:
        logger.info("Compiling graph with checkpointing enabled")
        return workflow.compile(checkpointer=checkpointer)
    else:
        logger.info("Compiling graph without checkpointing")
        return workflow.compile()

@traceable
async def run_enhancement_graph(
    field_name: str, 
    text: str, 
    db: Session,
    thread_id: str | None = None,
    use_checkpointing: bool = True,
    campaign_name: str | None = None
) -> dict:
    """Run the enhancement graph to improve text.
    
    Args:
        field_name: Name of the field being enhanced
        text: Original text to enhance
        db: Database session
        thread_id: Optional thread ID for checkpointing (enables state persistence)
        use_checkpointing: Whether to use checkpointing for state persistence
        campaign_name: Optional campaign name for context
    
    Returns:
        Dictionary with 'enhanced_text' and 'explanation' keys
    """

    config = _load_models_config()
    enhancement = config.get("models", {}).get("enhancement", {})
    moderation = config.get("models", {}).get("moderation", {})
    
    maritaca_api_key = (os.getenv("MARITACA_API_KEY") or "").strip()
    openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    temperature = float(enhancement.get("temperature", 0.5))
    max_tokens = int(enhancement.get("max_tokens", 2000))
    timeout = int(enhancement.get("timeout", 20))
    max_retries = int(enhancement.get("max_retries", 2))

    def _is_reasoning_model(name: str) -> bool:
        """Detecta modelos de raciocínio (OpenAI o-series e gpt-5)."""
        _lower = name.lower()
        return any(tag in _lower for tag in ("gpt-5", "o1", "o3", "o4"))

    # caso não tenha api key da MaritacaAI, usa OpenAI
    if maritaca_api_key:
        provider = "maritaca"
        model_name = enhancement.get("name", "sabiazinho-4")
        base_url = os.getenv("MARITACA_BASE_URL", enhancement.get("base_url", "https://chat.maritaca.ai/api"))
        api_key = maritaca_api_key
    else:
        provider = "openai"
        if not openai_api_key:
            raise ValueError("No MARITACA_API_KEY or OPENAI_API_KEY set in environment")
        model_name = enhancement.get("fallback_model_name", "gpt-5-nano")
        base_url = "https://api.openai.com/v1"
        api_key = openai_api_key

    if _is_reasoning_model(model_name):
        chat_model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            model_kwargs={"max_completion_tokens": max(max_tokens, 8000)},
        )
        logger.info(
            f"Reasoning model detected: '{model_name}' — "
            f"using max_completion_tokens={max(max_tokens, 8000)}, no temperature"
        )
    else:
        chat_model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
    
    logger.info(f"Using provider={provider}, model={model_name}, base_url={base_url}")
    LLM_INVOCATIONS.labels(provider=provider, model=model_name).inc()

    moderation_model = moderation.get("name", "omni-moderation-latest")
    moderation_check_input = moderation.get("check_input", True)
    moderation_check_output = moderation.get("check_output", False)
    moderation_exit_behavior = moderation.get("exit_behavior", "error")
    moderation_violation_message = moderation.get("violation_message", "O conteúdo fornecido viola as políticas de uso. Por favor, revise o texto e remova qualquer conteúdo inadequado. Categorias de violação: {categories}")
    
    moderation_middleware = OpenAIModerationMiddleware(
        model=moderation_model,
        check_input=moderation_check_input,
        check_output=moderation_check_output,
        exit_behavior=moderation_exit_behavior,
        violation_message=moderation_violation_message
    )
    
    agent = create_agent(
        model=chat_model,
        tools=[], 
        middleware=[moderation_middleware],
        response_format=EnhancedTextResponse,
    )
    
    checkpointer = None
    if use_checkpointing and thread_id:
        try:
            checkpointer = await get_checkpoint_saver()
            logger.info(f"Checkpointer initialized, will use thread_id: {thread_id}")
        except Exception as e:
            logger.error(f"Failed to initialize checkpointer: {e}", exc_info=True)
            logger.warning("Continuing without checkpointing due to initialization failure")
            checkpointer = None
            use_checkpointing = False  
    
    graph = create_enhancement_graph(db, agent, checkpointer=checkpointer)
    _start = time.perf_counter()

    if checkpointer and thread_id:
        initial_state: EnhancementGraphState = {
            "field_name": field_name,
            "text": text,
            "campaign_name": campaign_name,
        }
        config = {
            "configurable": {"thread_id": thread_id},
            "metadata": {
                "field_name": field_name,
                "campaign_name": campaign_name,
                "provider": provider,
                "model": model_name,
            },
            "tags": [field_name, provider],
        }
        try:
            logger.info(f"Invoking graph with checkpointing - thread_id: {thread_id}")
            logger.debug(f"Config: {config}")
            logger.debug(f"Initial state: {initial_state}")

            logger.info(f"[STATE] Estado ANTES da execução (thread_id: {thread_id})")
            logger.info(f"[STATE] - field_name: {initial_state.get('field_name')}")
            logger.info(f"[STATE] - text: {initial_state.get('text')[:100]}...")
            
            result = await graph.ainvoke(initial_state, config=config)
            
            logger.info(f"[STATE] Estado DEPOIS da execução (thread_id: {thread_id})")
            
            result_history = []
            if isinstance(result, dict):
                result_history = result.get("enhancement_history", [])
                logger.info(f"[STATE] - enhancement_history count: {len(result_history) if result_history else 0}")
                logger.info(f"[STATE] - enhanced_text length: {len(result.get('enhanced_text', ''))}")
                if result_history:
                    logger.info(f"[STATE] - Campos aprimorados: {[h.get('field_name') for h in result_history]}")

            logger.info(f"Graph execution completed successfully with checkpointing for thread_id: {thread_id}")
            logger.debug(f"Result type: {type(result)}, keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
        except Exception as e:
            logger.error(
                f"EXCEPTION in graph execution with checkpointing for thread_id {thread_id}",
                exc_info=True
            )
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception message: {str(e)}")
            logger.error(f"Exception args: {e.args if hasattr(e, 'args') else 'N/A'}")
            raise
    else:
        full_initial_state: EnhancementGraphState = {
            "field_name": field_name,
            "text": text,
            "field_info": None,
            "enhanced_text": None,
            "explanation": None,
            "enhancement_history": None,
            "previous_fields_summary": None,
            "campaign_name": campaign_name
        }
        no_cp_config = {
            "metadata": {
                "field_name": field_name,
                "campaign_name": campaign_name,
                "provider": provider,
                "model": model_name,
            },
            "tags": [field_name, provider],
        }
        result = await graph.ainvoke(full_initial_state, config=no_cp_config)
        logger.info("Graph execution completed without checkpointing")
    
    _elapsed = time.perf_counter() - _start
    enhanced_text = result.get("enhanced_text", "")
    explanation = result.get("explanation", "No enhancement was generated.")
    
    if not enhanced_text and explanation and "moderação" in explanation.lower():
        ENHANCEMENT_TOTAL.labels(field_name=field_name, provider=provider, status="moderation").inc()
        ENHANCEMENT_DURATION.labels(field_name=field_name, provider=provider).observe(_elapsed)
        return {
            "enhanced_text": "",
            "explanation": explanation,
            "llm_model": model_name,
        }
    
    ENHANCEMENT_TOTAL.labels(field_name=field_name, provider=provider, status="success").inc()
    ENHANCEMENT_DURATION.labels(field_name=field_name, provider=provider).observe(_elapsed)

    return {
        "enhanced_text": enhanced_text or text,
        "explanation": explanation,
        "llm_model": model_name,
    }


def _create_studio_graph():
    """Create a graph instance for LangGraph Studio visualization.
    
    Uses placeholder functions that allow the graph structure to be visualized
    without requiring actual database or LLM connections.
    """
    workflow = StateGraph(EnhancementGraphState)
    
    def fetch_node_stub(state: EnhancementGraphState):
        """Stub: in production, fetches field config from DB."""
        return {
            "field_info": {
                "display_name": state.get("field_name", "Campo"),
                "expectations": "Expectativas do campo (carregadas do banco)",
                "improvement_guidelines": "Diretrizes de melhoria (carregadas do banco)",
            },
            "previous_fields_summary": None,
            "enhancement_history": state.get("enhancement_history") or [],
            "campaign_name": state.get("campaign_name"),
        }
    
    def enhance_node_stub(state: EnhancementGraphState):
        """Stub: in production, calls LLM for enhancement."""
        return {
            "enhanced_text": f"[Texto aprimorado: {state.get('text', '')}]",
            "explanation": "Explicação gerada pelo LLM (sabiazinho-4 ou fallback).",
            "enhancement_history": (state.get("enhancement_history") or []) + [
                {
                    "field_name": state.get("field_name"),
                    "original_text": state.get("text"),
                    "enhanced_text": f"[Texto aprimorado]",
                    "explanation": "Stub",
                    "timestamp": "2026-01-29T00:00:00Z",
                }
            ],
        }
    
    workflow.add_node("fetch_field_info", fetch_node_stub)
    workflow.add_node("enhance_text", enhance_node_stub)
    
    workflow.set_entry_point("fetch_field_info")
    workflow.add_edge("fetch_field_info", "enhance_text")
    workflow.add_edge("enhance_text", END)
    
    return workflow.compile()


graph = _create_studio_graph()

