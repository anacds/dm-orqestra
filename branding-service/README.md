# Branding Service

Validação determinística de marca para emails HTML e imagens de app. Verifica paleta de cores, fontes, estrutura e presença de logo. Não usa LLM. Exposto exclusivamente via MCP.

Porta: 8012

## MCP Tools (Streamable HTTP em `/mcp`)

| Tool | Descrição |
|---|---|
| `validate_email_brand` | Valida HTML de email contra guidelines de marca |
| `validate_image_brand` | Valida cores dominantes de imagem contra paleta aprovada |
| `get_brand_guidelines` | Retorna as guidelines de marca vigentes |

## Execução manual

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8012
```

## Variáveis de ambiente

Nenhuma obrigatória. Opcionais: `PORT` (default 8012), `LOG_LEVEL` (default INFO).
