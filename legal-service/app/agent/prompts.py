from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

VALIDATION_SYSTEM_TEMPLATE = """Você é um assistente jurídico especializado em validação de comunicações.
Sua função é analisar o conteúdo da comunicação e determinar se ele atende às diretrizes jurídicas da empresa.

INSTRUÇÕES:
- Analise o conteúdo fornecido com base nas diretrizes fornecidas no contexto
- Determine se a comunicação está APROVADA ou REPROVADA (decision: APROVADO ou REPROVADO)
- Indique se requer revisão humana (true quando REPROVADO, false quando APROVADO)
- Forneça um resumo claro e objetivo das violações encontradas, limite a explicação a 400 caracteres
- Liste as fontes utilizadas na análise (sources)
- Tudo o que fizer parte do conteúdo (title, body ou imagens) deve ser considerado para a análise
- Para canal APP pode-se assumir que, ao clicar no banner/tela, mais detalhes serão exibidos ao cliente; avalie a conformidade somente do que está visível na imagem
- Não recomende melhorias para conteúdos aprovados

FORMATO DE RESPOSTA:
{format_instructions}"""

VALIDATION_HUMAN_TEMPLATE = """CONTEXTO E DIRETRIZES JURÍDICAS:
{context}

CANAL: {channel}

FONTES DE REFERÊNCIA: {sources}

Analise a seguinte comunicação:
{content_description}"""


def build_validation_messages(
    context: str,
    channel: str,
    sources: list[str],
    format_instructions: str,
    content_description: str,
    image: Optional[str] = None,
) -> list[BaseMessage]:
    sources_str = ", ".join(sources) if sources else "N/A"
    
    system_msg = SystemMessage(
        content=VALIDATION_SYSTEM_TEMPLATE.format(
            format_instructions=format_instructions
        )
    )
    
    human_text = VALIDATION_HUMAN_TEMPLATE.format(
        context=context,
        channel=channel or "N/A",
        sources=sources_str,
        content_description=content_description,
    )
    
    if not image:
        return [system_msg, HumanMessage(content=human_text)]
    
    parts: list[dict] = [
        {"type": "text", "text": human_text},
        {"type": "image_url", "image_url": {"url": image}},
    ]
    return [system_msg, HumanMessage(content=parts)]