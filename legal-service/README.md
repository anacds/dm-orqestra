# Legal Service

Validação jurídica de comunicações usando RAG (Weaviate + LangGraph). Busca normas regulatórias relevantes e emite parecer de conformidade. Expõe Agent Card A2A.

Porta: 8005

## Endpoints REST

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/legal/validate` | Validar comunicação |

## Protocolo A2A

| Rota | Descrição |
|---|---|
| GET | `/a2a/.well-known/agent-card.json` | Agent Card |
| POST | `/a2a/v1/message:send` | Receber mensagem A2A |

## Execução manual

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8005
```

Requer Weaviate rodando e populado com documentos jurídicos (ver `documents-ingestion/`).

## Variáveis de ambiente

Ver `env.example`.
