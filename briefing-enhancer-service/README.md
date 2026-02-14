# Briefing Enhancer Service

Aprimora objetivos de campanha usando LLM (OpenAI/Maritaca) com LangGraph. Recebe um briefing bruto e devolve versão refinada.

Porta: 8001

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/enhance-objective` | Aprimorar objetivo de campanha |
| PATCH | `/api/ai-interactions/{id}/decision` | Registrar decisão do usuário sobre sugestão |

## Execução manual

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8001
```

## Variáveis de ambiente

Ver `env.example`.
