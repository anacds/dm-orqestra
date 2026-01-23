import logging
from typing import Dict, Optional
from app.agent.state import AgentState
from app.agent.retriever import HybridWeaviateRetriever
from app.core.config import settings
from app.core.models_config import load_models_config

logger = logging.getLogger(__name__)


def retrieve_node(state: AgentState, retriever: HybridWeaviateRetriever) -> Dict:
    """Retrieve relevant documents from Weaviate for validation context."""
    task = state.get("task")
    channel = state.get("channel")
    content = state.get("content")
    content_title = state.get("content_title")
    content_body = state.get("content_body")
    
    # Usa content_body se disponível, senão usa content (backward compatibility)
    body_text = content_body or content
    
    if not task or not body_text:
        raise ValueError("task e content (ou content_body) são obrigatórios")
    
    # Constrói query baseada no canal
    if channel == "PUSH" and content_title and content_body:
        # Para PUSH com title/body separados, usa ambos na query
        query_text = f"{task} para {channel}: título: {content_title}, corpo: {content_body}"
    else:
        # Para SMS e outros, usa apenas body
        query_text = f"{task}: {body_text}"
        if channel:
            query_text = f"{task} para {channel}: {body_text}"
    
    logger.info(f"Retrieving documents for query: {query_text[:100]}...")
    
    config = load_models_config()
    retrieval_config = config.get("models", {}).get("retrieval", {})
    limit = retrieval_config.get("limit", 10)
    alpha = retrieval_config.get("alpha", 0.5)
    
    # Para PUSH com title/body, passa ambos para o retriever
    retrieved_chunks = retriever.hybrid_search(
        query=query_text,
        limit=limit,
        alpha=alpha,
        channel=channel,
        query_title=content_title if channel == "PUSH" else None,
        query_body=content_body if channel == "PUSH" else None,
    )
    
    context_parts = []
    sources = []
    
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        context_parts.append(chunk["text"])
        source = chunk.get("file_name", chunk.get("source_file", "unknown"))
        if source not in sources:
            sources.append(source)
        
        # Log chunks em modo DEBUG
        score_value = chunk.get('score')
        score_str = f"{score_value:.4f}" if score_value is not None else "N/A"
        logger.debug(
            f"[RETRIEVAL] Chunk {idx}/{len(retrieved_chunks)}: "
            f"file={source}, "
            f"channel={chunk.get('channel', 'N/A')}, "
            f"score={score_str}, "
            f"text_preview={chunk['text'][:100]}..."
        )
    
    context = "\n\n".join(context_parts)
    
    # Log resumo dos chunks recuperados em modo DEBUG
    logger.debug(
        f"[RETRIEVAL] Total de chunks recuperados: {len(retrieved_chunks)}, "
        f"fontes únicas: {len(sources)}, "
        f"tamanho total do contexto: {len(context)} caracteres"
    )
    
    return {
        "retrieved_chunks": retrieved_chunks,
        "context": context,
        "sources": sources,
        "search_metadata": {
            "num_chunks": len(retrieved_chunks),
            "query": query_text,
            "limit": limit,
            "alpha": alpha,
            "channel": channel,
        }
    }


def generate_node(state: AgentState, llm) -> Dict:
    """Generate validation decision using LLM with retrieved context."""
    from langchain_core.prompts import ChatPromptTemplate
    import json
    
    task = state.get("task")
    channel = state.get("channel")
    content = state.get("content")
    content_title = state.get("content_title")
    content_body = state.get("content_body")
    context = state.get("context", "")
    sources = state.get("sources", [])
    
    if not task or not content:
        raise ValueError("task e content são obrigatórios")
    
    if task == "VALIDATE_COMMUNICATION":
        from app.api.schemas import ValidationOutput
        from langchain_core.output_parsers import PydanticOutputParser
        
        output_parser = PydanticOutputParser(pydantic_object=ValidationOutput)
        
        # Constrói descrição do conteúdo baseado no canal
        if channel == "PUSH" and content_title and content_body:
            content_description = f"TÍTULO: {content_title}\n\nCORPO: {content_body}"
        else:
            content_description = content
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um assistente jurídico especializado em validação de comunicações.

Sua função é analisar o conteúdo da comunicação e determinar se ele atende às diretrizes jurídicas da empresa.
Para isso, utilize as informações de contexto referentes ao canal específico + guidelines gerais de linguagem promocional e uso de dados pessoais.

INSTRUÇÕES:
- Analise o conteúdo fornecido com base nas diretrizes no contexto
- Determine se a comunicação está APROVADA ou REPROVADA
- Classifique a severidade: BLOCKER (bloqueia envio), WARNING (requer atenção), INFO (aprovado com observações)
- Indique se requer revisão humana (true para BLOCKER e WARNING críticos)
- Forneça um resumo claro e objetivo das violações encontradas
- Liste as fontes utilizadas na análise
- Tudo o que fizer parte do conteúdo (title ou body) deve ser considerado para a análise.

CRITÉRIOS CRÍTICOS (devem resultar em REPROVADO/BLOCKER):
- Ausência de identificação da marca "Orqestra" na comunicação
- Exposição de dados sensíveis (CPF completo, números de documentos, informações financeiras detalhadas)
- Claims promocionais absolutos ou enganosos
- Falta de opt-out quando necessário
- Links suspeitos ou não verificados

CONTEXTO (Diretrizes):
{context}

Canal: {channel}
FONTES: {sources}

{format_instructions}"""),
            ("human", "Analise a seguinte comunicação:\n\n{content_description}"),
        ])
        
        formatted_prompt = prompt.format_messages(
            context=context,
            channel=channel or "N/A",
            sources=", ".join(sources) if sources else "N/A",
            content_description=content_description,
            format_instructions=output_parser.get_format_instructions(),
        )
        
        logger.info("Generating structured validation response...")
        
        try:
            if hasattr(llm, 'with_structured_output'):
                structured_llm = llm.with_structured_output(
                    ValidationOutput,
                    method="json_mode"
                )
                result = structured_llm.invoke(formatted_prompt)
                
                return {
                    "decision": result.decision,
                    "severity": result.severity,
                    "requires_human_review": result.requires_human_review,
                    "summary": result.summary,
                    "sources": result.sources if result.sources else sources,
                }
            else:
                response = llm.invoke(formatted_prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
                parsed = output_parser.parse(response_text)
                
                return {
                    "decision": parsed.decision,
                    "severity": parsed.severity,
                    "requires_human_review": parsed.requires_human_review,
                    "summary": parsed.summary,
                    "sources": parsed.sources if parsed.sources else sources,
                }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in structured output: {e}", exc_info=True)
            
            is_token_limit = (
                "length limit" in error_msg.lower() or
                "max_tokens" in error_msg.lower() or
                "token limit" in error_msg.lower() or
                "completion_tokens" in error_msg.lower()
            )
            
            if is_token_limit:
                summary = "A análise da comunicação excedeu o limite de processamento. Por favor, revise manualmente a comunicação para garantir conformidade com as diretrizes."
            else:
                summary = f"Erro ao processar resposta do LLM. Por favor, revise manualmente a comunicação."
            
            return {
                "decision": "REPROVADO",
                "severity": "BLOCKER",
                "requires_human_review": True,
                "summary": summary,
                "sources": sources,
            }
    
    raise ValueError(f"Task '{task}' não é suportada")


def should_continue_node(state: AgentState) -> str:
    """Determine whether to continue or end the workflow."""
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if iteration_count >= max_iterations:
        return "end"
    
    return "continue"

