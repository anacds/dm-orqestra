# API Gateway

Proxy reverso centralizado que roteia requests para os serviços backend, aplica autenticação JWT e rate limiting.

Porta: 8000

## Roteamento

| Prefixo | Serviço destino |
|---|---|
| `/api/auth` | Auth Service (8002) |
| `/api/campaigns` | Campaigns Service (8003) |
| `/api/ai/analyze-piece`, `/api/ai/generate-text` | Content Validation Service (8004) |
| `/api/enhance-objective`, `/api/ai-interactions`, `/api/ai` | Briefing Enhancer Service (8001) |

## Execução manual

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Variáveis de ambiente

Ver `env.example`.
