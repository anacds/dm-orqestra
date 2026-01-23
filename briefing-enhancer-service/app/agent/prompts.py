from langsmith import traceable

SYSTEM_PROMPT = """Você é um especialista em aprimoramento de textos para campanhas de CRM.
Seu trabalho é aprimorar textos seguindo diretrizes específicas para cada tipo de campo.
Analise o texto original e forneça uma versão aprimorada que seja mais clara, específica e alinhada com as expectativas do campo."""

@traceable
def build_enhancement_prompt(
    display_name: str,
    field_name: str,
    expectations: str,
    guidelines: str,
    original_text: str,
    previous_fields_summary: str | None = None,
    campaign_name: str | None = None
) -> str:
    """Build enhancement prompt with field-specific guidelines and context.
    
    Args:
        display_name: Human-readable field name
        field_name: Technical field name
        expectations: What is expected for this field
        guidelines: Specific improvement guidelines
        original_text: Text to enhance
        previous_fields_summary: Summary of previously enhanced fields for consistency
        campaign_name: Optional campaign name
    
    Returns:
        Formatted prompt string for the LLM
    """
    campaign_section = ""
    
    if campaign_name:
        campaign_section = f"""Nome da Campanha: {campaign_name}"""
        context_section = ""

    if previous_fields_summary:
        context_section = f"""Contexto de campos anteriores aprimorados nesta sessão:{previous_fields_summary}
IMPORTANTE: Use o contexto acima para garantir consistência entre os campos. O texto aprimorado deve ser coerente com os campos anteriores já aprimorados nesta mesma campanha.
"""
    
    return f"""
{campaign_section}Contexto do campo:
- Nome: {display_name} ({field_name})
- O que se espera: {expectations}
- Diretrizes de melhoria: {guidelines}
{context_section}
Texto original:
{original_text}

Aprimore este texto seguindo as diretrizes. O texto aprimorado deve:
1. Ser mais claro e específico
2. Eliminar ambiguidades e termos vagos
3. Seguir as expectativas e diretrizes fornecidas
4. Manter o sentido original, mas com melhorias significativas
5. Não inventar dados/informações que não estão no texto original
6. Não definir valores ou números, apenas placeholders (a não ser que os valores estejam no texto original). Por exemplo, 'aumento de [X%] no próximo [mês/trimestre/ano]' ou 'clientes entre [X e Y] anos'.
{f"7. Ser consistente com os campos anteriores já aprimorados nesta campanha" if previous_fields_summary else ""}

IMPORTANTE: 
- O texto aprimorado deve ter no máximo 300 caracteres.
- A explicação deve ter no máximo 300 caracteres e ser clara e concisa.

Forneça o texto aprimorado e uma explicação clara e concisa do que precisava de melhoria e por quê."""

