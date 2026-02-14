import logging
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount
from app.services import BrandValidator, validate_email_branding, validate_image_branding

logger = logging.getLogger(__name__)


mcp = FastMCP(
    "branding-service",
    instructions="""
    MCP server que expõe validações da marca Orqestra    
    """,
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def validate_email_brand(html: str) -> Dict[str, Any]:
    """
    Valida HTML de email contra as diretrizes de marca da Orqestra.
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
async def validate_image_brand(image: str) -> Dict[str, Any]:
    """
    Valida as cores dominantes de uma imagem contra a paleta da marca Orqestra.
    """
    logger.info("validate_image_brand: validating image (%d chars)", len(image))

    try:
        result = validate_image_branding(image)
        logger.info(
            "validate_image_brand: compliant=%s, score=%d, violations=%d",
            result["compliant"],
            result["score"],
            result["summary"]["total"],
        )
        return result
    except Exception as e:
        logger.error("validate_image_brand error: %s", e)
        return {
            "compliant": False,
            "score": 0,
            "violations": [
                {
                    "rule": "validation_error",
                    "category": "system",
                    "severity": "critical",
                    "value": "",
                    "message": f"Erro ao validar imagem: {str(e)}",
                }
            ],
            "summary": {"critical": 1, "warning": 0, "info": 0, "total": 1},
            "dominant_colors": [],
        }


@mcp.tool()
async def get_brand_guidelines() -> Dict[str, Any]:
    """
    Retorna as diretrizes de marca da Orqestra para referência.
    """
    return BrandValidator.get_guidelines()


def build_mcp_app() -> Starlette:
    return Starlette(
        routes=[Mount("/", app=mcp.streamable_http_app())],
    )
