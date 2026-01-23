# Briefing Enhancer Service

Microsserviço de IA para aprimoramento de texto do Orqestra usando LangGraph e OpenAI.

## Status

✅ Integrado com LangGraph e OpenAI. O serviço usa um workflow em grafo para aprimorar textos baseado em expectativas e diretrizes específicas de cada campo.

## Arquitetura

O serviço usa **LangGraph** para criar um workflow em grafo que:

1. **Busca informações do campo** (`fetch_field_info`): Consulta o banco de dados PostgreSQL para obter expectativas e diretrizes específicas do campo a ser aprimorado.
2. **Aprimora o texto** (`enhance_text`): Usa OpenAI (via LangChain) para aprimorar o texto seguindo as diretrizes específicas do campo.
3. **Formata a resposta** (`format_response`): Estrutura a resposta final com texto aprimorado e explicação.

## Estrutura

```
briefing-enhancer-service/
├── app/
│   ├── api/
│   │   ├── routes.py          # Endpoints HTTP
│   │   ├── services.py        # Lógica de negócio (usa LangGraph)
│   │   └── schemas.py         # Schemas Pydantic
│   ├── core/
│   │   ├── config.py          # Configurações (inclui OpenAI)
│   │   └── database.py        # Configuração SQLAlchemy
│   ├── graph/
│   │   ├── graph.py              # Grafo principal do LangGraph (inclui criação do agente LLM)
│   │   ├── nodes.py              # Nós do grafo (fetch, enhance, format)
│   │   └── state.py              # Estado do grafo (TypedDict)
│   └── models/
│       └── enhanceable_field.py  # Model SQLAlchemy para campos melhoráveis
├── alembic/                   # Migrations do banco de dados
│   ├── versions/
│   │   └── 001_initial_schema.py  # Migration inicial com campos
│   └── env.py
├── main.py                    # Entry point
├── requirements.txt
└── Dockerfile
```

## Banco de Dados

O serviço usa PostgreSQL com uma tabela `enhanceable_fields` que armazena:
- `field_name`: Identificador do campo (ex: "businessObjective", "expectedResult")
- `display_name`: Nome exibido do campo
- `expectations`: O que se espera deste campo
- `improvement_guidelines`: Diretrizes de melhoria para o agente IA

Campos pré-configurados:
- `businessObjective` - Objetivo de Negócio
- `expectedResult` - Resultado Esperado / KPI Principal
- `targetAudienceDescription` - Descrição do Público-Alvo
- `exclusionCriteria` - Critérios de Exclusão

## Endpoints

### POST /api/enhance-objective
Aprimora texto usando LangGraph e OpenAI.

**Request:**
```json
{
  "text": "Texto a ser aprimorado",
  "field_name": "businessObjective"
}
```

**Response:**
```json
{
  "enhancedText": "Texto aprimorado",
  "explanation": "Explicação das mudanças"
}
```

**Campos suportados:**
- `businessObjective`
- `expectedResult`
- `targetAudienceDescription`
- `exclusionCriteria`

### GET /api/health
Health check do serviço.

## Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` baseado em `env.example`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/briefing_enhancer

# OpenAI
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
```

## Desenvolvimento

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar migrations
alembic upgrade head

# Rodar localmente
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Migrations

```bash
# Criar nova migration
alembic revision --autogenerate -m "description"

# Aplicar migrations
alembic upgrade head

# Reverter última migration
alembic downgrade -1
```

## Docker

```bash
# Build
docker build -t briefing-enhancer-service .

# Executar
docker run -p 8001:8001 briefing-enhancer-service
```

## Tecnologias

- **FastAPI**: Framework web
- **LangGraph**: Workflow em grafo para IA
- **LangChain**: Integração com LLMs
- **OpenAI**: LLM provider
- **SQLAlchemy**: ORM
- **Alembic**: Migrations
- **PostgreSQL**: Banco de dados

