# Content Validation Service

Orquestrador de validação de peças criativas usando LangGraph. Valida formato, specs técnicos, branding (via MCP) e compliance jurídico (via A2A). Expõe também um Agent Card A2A.

Porta: 8004

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/ai/analyze-piece` | Validar peça criativa (cache transparente para SMS/PUSH) |
| POST | `/api/ai/generate-text` | Gerar texto para canal |

## Protocolo A2A

| Rota | Descrição |
|---|---|
| GET | `/a2a/.well-known/agent-card.json` | Agent Card |
| POST | `/a2a/v1/message:send` | Receber mensagem A2A |

## Integração com outros serviços

- **Campaigns Service** (MCP): busca conteúdo de peças e specs de canais
- **Branding Service** (MCP): validação determinística de marca (email/app)
- **HTML Converter** (MCP): converte HTML de email para imagem
- **Legal Service** (A2A): validação jurídica de comunicações

## Execução manual

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8004
```

## Variáveis de ambiente

Ver `env.example`.
