SYSTEM_PROMPT = """Você é um especialista em aprimoramento de textos para campanhas de CRM.

PRINCÍPIOS FUNDAMENTAIS:
1. Preserve SEMPRE valores numéricos, percentuais, métricas e prazos que existem no texto original
2. Use placeholders [como este] APENAS para informações que NÃO existem no original
3. Nunca substitua dados concretos por placeholders (ex: "15%" -> "[X%]")
4. Torne textos vagos mais específicos e mensuráveis
5. Mantenha o sentido original sem inventar informações
"""

def build_enhancement_prompt(
    display_name: str,
    field_name: str,
    expectations: str,
    guidelines: str,
    original_text: str,
    previous_fields_summary: str | None = None,
    campaign_name: str | None = None
) -> str:
    campaign_section = ""
    
    if campaign_name:
        campaign_section = f"""Nome da Campanha: {campaign_name}"""
        context_section = ""

    if previous_fields_summary:
        context_section = f"""Contexto de campos anteriores aprimorados nesta sessão:{previous_fields_summary}
IMPORTANTE: Use o contexto acima para garantir consistência entre os campos. O texto aprimorado deve ser coerente com os campos anteriores já aprimorados nesta mesma campanha.
"""
    
    return f"""{campaign_section}
Campo: {display_name} ({field_name})
Expectativa: {expectations}
Diretrizes: {guidelines}

{context_section}

Texto original:
{original_text}

Forneça:
1. Texto aprimorado (máx. 300 chars)
2. Explicação das melhorias (máx. 300 chars)"""

