import logging
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.enhanceable_field import EnhanceableField
from app.agent.state import EnhancementGraphState, FieldEnhancement
from app.agent.prompts import build_enhancement_prompt, SYSTEM_PROMPT
from langchain_core.runnables import Runnable
from langchain_core.exceptions import LangChainException
from langchain_openai.middleware import OpenAIModerationError
from openai import APITimeoutError, RateLimitError, APIError
from app.agent.schemas import EnhancedTextResponse
from app.core.metrics import MODERATION_REJECTIONS

logger = logging.getLogger(__name__)

def _build_previous_fields_summary(history: list[FieldEnhancement] | None) -> str | None:
    """Build summary of previously enhanced fields for context consistency."""
    if not history or len(history) == 0:
        return None
    
    summary_parts = []
    
    for enhancement in history:
        field_name = enhancement.get("field_name", "unknown")
        enhanced_text = enhancement.get("enhanced_text", "")
        if len(enhanced_text) > 200:
            enhanced_text = enhanced_text[:200] + "..."
        summary_parts.append(f"- {field_name}: {enhanced_text}")
    
    return "\n".join(summary_parts)


def fetch_field_info(state: EnhancementGraphState, db: Session) -> Dict:
    """Fetch field configuration from database and prepare context.
    """
    field_name = state["field_name"]
    
    logger.info(f"Fetching field info for field: {field_name}")

    history = state.get("enhancement_history") or []
    field = db.query(EnhanceableField).filter(EnhanceableField.field_name == field_name).first()
    
    if not field:
        logger.warning(f"Field '{field_name}' not found in database, using default guidelines")
        field_info_dict = {
            "display_name": field_name,
            "expectations": "Melhore o preenchimento do campo para que seja claro, específico e bem estruturado.",
            "improvement_guidelines": "Melhore a clareza, especificidade e estrutura do texto."
        }
    else:
        logger.debug(f"Found field info for '{field_name}': {field.display_name}")
        field_info_dict = {
            "display_name": field.display_name,
            "expectations": field.expectations,
            "improvement_guidelines": field.improvement_guidelines or ""
        }
    
    previous_summary = _build_previous_fields_summary(history)
    if previous_summary:
        logger.info(f"Found {len(history)} previous field enhancements in session history")
    
    campaign_name = state.get("campaign_name")
    
    return {
        "field_info": field_info_dict,
        "previous_fields_summary": previous_summary,
        "enhancement_history": history,  
        "campaign_name": campaign_name  
    }


def enhance_text(state: EnhancementGraphState, structured_llm: Runnable[Any, EnhancedTextResponse]) -> Dict:
    """Enhance text using LLM agent with field-specific guidelines.
    """
    field_info = state.get("field_info", {})
    original_text = state["text"]
    field_name = state["field_name"]
    previous_summary = state.get("previous_fields_summary")
    history = state.get("enhancement_history") or []
    campaign_name = state.get("campaign_name")
    
    prompt = build_enhancement_prompt(
        display_name=field_info.get("display_name", field_name),
        field_name=field_name,
        expectations=field_info.get("expectations", ""),
        guidelines=field_info.get("improvement_guidelines", ""),
        original_text=original_text,
        previous_fields_summary=previous_summary,
        campaign_name=campaign_name
    )
    
    logger.debug(f"[PROMPT] Used prompt (field: {field_name})")
    logger.debug(f"[PROMPT] {prompt}")
    
    try:
        logger.info(f"Enhancing text for field '{field_name}' (text length: {len(original_text)} chars)")
        
        agent_result = structured_llm.invoke({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        })
        
        result = agent_result.get("structured_response", agent_result) if isinstance(agent_result, dict) else agent_result
        
        logger.info(f"Successfully enhanced text for field '{field_name}' (enhanced length: {len(result.enhanced_text)} chars)")
        logger.debug(f"Enhancement explanation: {result.explanation[:100]}...")
        
        new_enhancement: FieldEnhancement = {
            "field_name": field_name,
            "original_text": original_text,
            "enhanced_text": result.enhanced_text,
            "explanation": result.explanation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        updated_history = list(history) + [new_enhancement]
        
        return {
            "enhanced_text": result.enhanced_text,
            "explanation": result.explanation,
            "enhancement_history": updated_history
        }
    except OpenAIModerationError as e:
        MODERATION_REJECTIONS.labels(field_name=field_name).inc()
        logger.warning(f"Content moderation error for field '{field_name}': {str(e)}")
        return {
            "enhanced_text": "",
            "explanation": f"O conteúdo fornecido foi rejeitado pela moderação de segurança. Por favor, revise o texto e remova qualquer conteúdo inadequado. Detalhes: {str(e)}"
        }
    except (APITimeoutError, LangChainException) as e:
        error_message = str(e).lower()
        logger.error(f"Timeout error for field '{field_name}': {str(e)}")
        if isinstance(e, LangChainException) and "timeout" not in error_message:
            return {
                "enhanced_text": original_text,
                "explanation": f"Erro no processamento: {str(e)}"
            }
        return {
            "enhanced_text": original_text,
            "explanation": "O processamento excedeu o tempo limite. O texto pode ser muito longo ou complexo. Tente dividir o texto em partes menores ou simplificar o conteúdo."
        }
    except RateLimitError as e:
        logger.warning(f"OpenAI rate limit exceeded for field '{field_name}': {str(e)}")
        return {
            "enhanced_text": original_text,
            "explanation": "Limite de requisições da API foi atingido. Por favor, tente novamente em alguns instantes."
        }
    except APIError as e:
        error_message = str(e).lower()
        logger.error(f"OpenAI API error for field '{field_name}': {str(e)}")
        if any(keyword in error_message for keyword in ["max_tokens", "token", "length"]):
            return {
                "enhanced_text": original_text,
                "explanation": "O texto é muito longo e excedeu o limite de tokens. Tente reduzir o tamanho do texto ou dividir em partes menores."
            }
        
        return {
            "enhanced_text": original_text,
            "explanation": f"Erro na API: {str(e)}"
        }
    except Exception as e:
        logger.exception(f"Unexpected error enhancing text for field '{field_name}': {str(e)}")
        return {
            "enhanced_text": original_text,
            "explanation": f"Erro ao processar com LLM: {str(e)}"
        }

