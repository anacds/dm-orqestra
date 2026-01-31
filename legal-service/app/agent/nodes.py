import logging
from typing import Dict
from app.agent.state import AgentState
from app.agent.retriever import HybridWeaviateRetriever
from app.agent.prompts import build_validation_messages
from app.core.config import settings
from app.core.models_config import load_models_config
from app.api.schemas import ValidationOutput
from langchain_core.output_parsers import PydanticOutputParser

logger = logging.getLogger(__name__)

def retrieve_node(state: AgentState, retriever: HybridWeaviateRetriever) -> Dict:
    """Retrieve relevant documents from Weaviate for validation context."""
    task = state.get("task")
    channel = state.get("channel")
    content = state.get("content")
    content_title = state.get("content_title")
    content_body = state.get("content_body")
    content_image = state.get("content_image")
    body_text = content_body or content

    if not task:
        raise ValueError("task é obrigatório")
    
    # --- CÓDIGO LEGADO: apenas APP usava content_image ---
    # if channel != "APP" and not body_text:
    #     raise ValueError("content (ou content_body) é obrigatório para canais além de APP")
    # if channel == "APP" and not content_image:
    #     raise ValueError("Para APP, informe content_image")
    # --- FIM CÓDIGO LEGADO ---
    
    # EMAIL agora pode ter content_image (análise visual)
    if channel == "APP" and not content_image:
        raise ValueError("Para APP, informe content_image")
    if channel == "EMAIL" and not content_image and not body_text:
        raise ValueError("Para EMAIL, informe content_image ou content_body")
    if channel not in ("APP", "EMAIL") and not body_text:
        raise ValueError("content (ou content_body) é obrigatório para canais além de APP/EMAIL com imagem")

    if channel == "PUSH" and content_title and content_body:
        query_text = f"{task} para {channel}: título: {content_title}, corpo: {content_body}"
    elif channel == "EMAIL" and content_image:
        # EMAIL com imagem: busca diretrizes visuais (similar a APP)
        query_text = f"{task} para {channel}: diretrizes para comunicação visual de e-mail, layout, creatives"
    elif channel == "EMAIL" and content_body:
        # --- CÓDIGO LEGADO: EMAIL com HTML/texto ---
        query_text = f"{task} para {channel}: corpo: {content_body}"
    elif channel == "APP" and content_image:
        query_text = f"{task} para {channel}: diretrizes para comunicação in-app, telas, creatives"
    else:
        query_text = f"{task}: {body_text}"
        if channel:
            query_text = f"{task} para {channel}: {body_text}"

    logger.info(f"Retrieving documents for query: {query_text[:100]}...")

    config = load_models_config()
    retrieval_config = config.get("models", {}).get("retrieval", {})
    limit = retrieval_config.get("limit", 10)
    alpha = retrieval_config.get("alpha", 0.5)

    use_title_body = channel == "PUSH" and content_title and content_body
    retrieved_chunks = retriever.hybrid_search(
        query=query_text,
        limit=limit,
        alpha=alpha,
        channel=channel,
        query_title=content_title if use_title_body else None,
        query_body=(content_body or content or "") if use_title_body else None,
    )
    
    context_parts = []
    sources = []
    
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        context_parts.append(chunk["text"])
        source = chunk.get("file_name", chunk.get("source_file", "unknown"))
        if source not in sources:
            sources.append(source)
        
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


def generate_node(
    state: AgentState,
    channel_to_llm: dict,
    default_llm,
) -> Dict:
    """Generate validation decision using LLM with retrieved context."""
    task = state.get("task")
    channel = state.get("channel")
    content = state.get("content")
    content_title = state.get("content_title")
    content_body = state.get("content_body")
    content_image = state.get("content_image")
    context = state.get("context", "")
    sources = state.get("sources", [])

    if not task:
        raise ValueError("task é obrigatório")
    
    # --- CÓDIGO LEGADO: apenas APP usava content_image ---
    # if channel != "APP" and not content:
    #     raise ValueError("content é obrigatório para canais além de APP")
    # if channel == "APP" and not content_image:
    #     raise ValueError("Para APP, informe content_image")
    # --- FIM CÓDIGO LEGADO ---
    
    # --- CÓDIGO LEGADO: EMAIL aceitava apenas image OU content ---
    # if channel == "EMAIL" and not content_image and not content:
    #     raise ValueError("Para EMAIL, informe content_image ou content")
    # --- FIM CÓDIGO LEGADO ---
    
    # EMAIL agora pode ter content_image E/OU content (análise visual + textual)
    if channel == "APP" and not content_image:
        raise ValueError("Para APP, informe content_image")
    if channel == "EMAIL" and not content_image and not content:
        raise ValueError("Para EMAIL, informe content_image e/ou content")
    if channel not in ("APP", "EMAIL") and not content:
        raise ValueError("content é obrigatório para canais além de APP/EMAIL")

    # --- CÓDIGO LEGADO: selecionava LLM apenas pelo canal ---
    # llm = channel_to_llm.get(channel) if channel else None
    # --- FIM CÓDIGO LEGADO ---
    
    # EMAIL com imagem usa modelo de fallback (APP) que suporta visão
    if channel == "EMAIL" and content_image:
        llm = channel_to_llm.get("APP")  # Usa modelo do APP (OpenAI com visão)
        logger.info("EMAIL com imagem: usando LLM de fallback (APP) - %s", llm.model_name if llm else "default")
    else:
        llm = channel_to_llm.get(channel) if channel else None
    
    if llm is None:
        llm = default_llm
    if channel:
        logger.info("Usando LLM do canal %s - %s", channel, llm.model_name)

    if task == "VALIDATE_COMMUNICATION":
        output_parser = PydanticOutputParser(pydantic_object=ValidationOutput)

        if channel == "PUSH" and content_title and content_body:
            content_description = f"TÍTULO: {content_title}\n\nCORPO: {content_body}"
        elif channel == "EMAIL" and content_image and content_body:
            # EMAIL com HTML + imagem (análise visual e textual)
            content_description = f"CORPO DO E-MAIL:\n{content_body}\n\n[1 imagem anexa do e-mail renderizado para análise visual]"
        elif channel == "EMAIL" and content_image:
            # EMAIL apenas com imagem
            content_description = "Comunicação de e-mail (1 imagem anexa do e-mail renderizado)."
        elif channel == "EMAIL" and content_body:
            # --- CÓDIGO LEGADO: EMAIL apenas com HTML/texto ---
            content_description = f"CORPO (HTML): {content_body}"
        elif channel == "APP":
            content_description = "Comunicação in-app (1 imagem anexa)."
        else:
            content_description = content or ""

        # --- CÓDIGO LEGADO: apenas APP enviava imagem ---
        # image=content_image if channel == "APP" else None
        # --- FIM CÓDIGO LEGADO ---
        
        # EMAIL e APP agora podem enviar imagem
        image_to_send = content_image if channel in ("APP", "EMAIL") and content_image else None

        messages = build_validation_messages(
            context=context,
            channel=channel or "N/A",
            sources=sources,
            format_instructions=output_parser.get_format_instructions(),
            content_description=content_description,
            image=image_to_send,
        )

        logger.info("Generating structured validation response...")

        try:
            if hasattr(llm, "with_structured_output"):
                structured_llm = llm.with_structured_output(
                    ValidationOutput,
                    method="json_mode",
                )
                result = structured_llm.invoke(messages)
                return {
                    "decision": result.decision,
                    "requires_human_review": result.requires_human_review,
                    "summary": result.summary,
                    "sources": result.sources if result.sources else sources,
                }
            else:
                response = llm.invoke(messages)
                response_text = response.content if hasattr(response, 'content') else str(response)
                parsed = output_parser.parse(response_text)
                
                return {
                    "decision": parsed.decision,
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
                "requires_human_review": True,
                "summary": summary,
                "sources": sources,
            }
    
    raise ValueError(f"Task '{task}' não é suportada")
