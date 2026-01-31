from typing import Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

VALIDATION_SYSTEM_TEMPLATE = """Você é um assistente jurídico especializado em validação de comunicações.
Sua função é analisar o conteúdo da comunicação e determinar se ele atende às diretrizes jurídicas da empresa.
Para isso, utilize as informações de contexto referentes ao canal específico.

INSTRUÇÕES:
- Analise o conteúdo fornecido com base nas diretrizes no contexto
- Determine se a comunicação está APROVADA ou REPROVADA (decision: APROVADO ou REPROVADO)
- Indique se requer revisão humana (true quando REPROVADO, false quando APROVADO)
- Forneça um resumo claro e objetivo das violações encontradas, limite a explicação a 400 caracteres.
- Liste as fontes utilizadas na análise (sources)
- Tudo o que fizer parte do conteúdo (title, body ou imagens) deve ser considerado para a análise.
- Para canal APP pode-se assumir que, ao clicar no banner/tela, mais detalhes serão exibidos ao cliente; avalie a conformidade somente do que está visível na imagem.

CONTEXTO E DIRETRIZES: {context}
CANAL: {channel}
FONTES: {sources}
INSTRUÇÕES DE FORMATO: {format_instructions}"""

VALIDATION_HUMAN_TEMPLATE = """Analise a seguinte comunicação:

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
    system = VALIDATION_SYSTEM_TEMPLATE.format(
        context=context,
        channel=channel or "N/A",
        sources=sources_str,
        format_instructions=format_instructions,
    )
    system_msg = SystemMessage(content=system)

    text = VALIDATION_HUMAN_TEMPLATE.format(content_description=content_description)
    if not image:
        return [system_msg, HumanMessage(content=text)]

    parts: list[dict] = [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": image}},
    ]
    return [system_msg, HumanMessage(content=parts)]
