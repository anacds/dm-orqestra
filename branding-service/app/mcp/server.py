"""
MCP Server configuration and tools for branding validation.
"""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

from app.services import validate_email_branding

logger = logging.getLogger(__name__)


mcp = FastMCP(
    "branding-service",
    instructions="""
    MCP server que expõe validações determinísticas de marca Orqestra para emails HTML.
    
    Este serviço NÃO usa IA/LLM - todas as validações são regras determinísticas baseadas
    no brand guideline da Orqestra.
    
    Validações incluem:
    - Cores: paleta aprovada, presença de cor primária
    - Tipografia: fontes aprovadas, tamanhos mínimos
    - Logo: presença, tamanho, alt text
    - Layout: largura do container, background
    - CTAs: cores corretas nos botões
    - Footer: copyright, link de descadastro
    - Elementos proibidos: animações blink, rotações excessivas
    """,
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def validate_email_brand(html: str) -> Dict[str, Any]:
    """
    Valida HTML de email contra as diretrizes de marca da Orqestra.
    
    Validação 100% determinística (sem IA/LLM). Verifica:
    - Cores: paleta aprovada (#6B7FFF, #8B9FFF, neutras)
    - Tipografia: fontes aprovadas (Arial, Helvetica, sans-serif), tamanho mínimo 12px
    - Logo: presença, tamanho (40-80px), alt text com "Orqestra"
    - Layout: largura máxima 600px, background neutro
    - CTAs: cor primária no background, texto branco
    - Footer: copyright "© Orqestra", link de descadastro
    - Proibidos: animações blink, text-shadow, rotações > 2°
    
    Args:
        html: Conteúdo HTML do email a ser validado
        
    Returns:
        Dict com:
        - compliant: bool - se está em conformidade (0 critical, 0 warning)
        - score: int - pontuação 0-100 (-20 por critical, -5 por warning)
        - violations: lista de violações encontradas
        - summary: contagem por severidade (critical, warning, info)
    """
    logger.info("validate_email_brand: validating HTML (%d chars)", len(html))
    
    try:
        result = validate_email_branding(html)
        logger.info(
            "validate_email_brand: compliant=%s, score=%d, violations=%d",
            result['compliant'],
            result['score'],
            result['summary']['total']
        )
        return result
    except Exception as e:
        logger.error("validate_email_brand error: %s", e)
        return {
            'compliant': False,
            'score': 0,
            'violations': [{
                'rule': 'validation_error',
                'category': 'system',
                'severity': 'critical',
                'value': '',
                'message': f'Erro ao validar HTML: {str(e)}'
            }],
            'summary': {'critical': 1, 'warning': 0, 'info': 0, 'total': 1}
        }


@mcp.tool()
async def get_brand_guidelines() -> Dict[str, Any]:
    """
    Retorna as diretrizes de marca da Orqestra para referência.
    
    Útil para consultar quais cores, fontes e regras são aplicadas
    nas validações de email.
    
    Returns:
        Dict com todas as diretrizes de marca (cores, fontes, regras).
    """
    return {
        'colors': {
            'primary': ['#6B7FFF', '#8B9FFF'],
            'neutrals': ['#FFFFFF', '#F5F5F5', '#F8F9FF'],
            'text': ['#333333', '#555555', '#666666', '#888888', '#999999', '#CCCCCC'],
            'dark': ['#000000', '#1A1A1A', '#2A2A2A', '#0A0A0A']
        },
        'typography': {
            'approved_fonts': ['Arial', 'Helvetica', 'sans-serif'],
            'prohibited_fonts': [
                'Times', 'Times New Roman', 'Georgia', 'serif',
                'Comic Sans', 'Comic Sans MS',
                'Courier', 'Courier New',
                'Impact', 'Papyrus', 'Brush Script'
            ],
            'min_font_size': '12px'
        },
        'logo': {
            'min_height': '40px',
            'max_height': '80px',
            'required_alt_text': 'Orqestra'
        },
        'layout': {
            'max_container_width': '600px',
            'allowed_backgrounds': ['#FFFFFF', '#F5F5F5', '#000000']
        },
        'cta': {
            'background_color': '#6B7FFF',
            'text_color': '#FFFFFF'
        },
        'footer': {
            'required_copyright': '© 2026 Orqestra',
            'required_unsubscribe': True
        },
        'prohibited': {
            'blink_animations': True,
            'text_shadow': True,
            'max_rotation': '2deg'
        }
    }


def build_mcp_app() -> Starlette:
    """Build Starlette app with MCP routes."""
    return Starlette(
        routes=[Mount("/", app=mcp.streamable_http_app())],
    )
