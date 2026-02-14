# Orqestra

Plataforma de gerenciamento de campanhas de CRM com validação automatizada de conteúdo. Combina microserviços REST, agentes baseados em LangGraph, comunicação via MCP (Model Context Protocol) e A2A (Agent-to-Agent Protocol).

> [!IMPORTANT]
> **Documentação completa:** [`dm_orqestra-ana-silva.pdf`](./dm_orqestra-ana-silva).
> Consulte a documentação em anexo para explicações sobre a Arquitetura do projeto, funcionalidades, detalhes da implementação, justificativas detalhadas e melhorias futuras.

## Arquitetura

```mermaid
graph TD
    FE["Frontend React :3000"]
    GW["API Gateway :8000"]

    AUTH["Auth :8002"]
    CAMP["Campaigns :8003"]
    BRIEF["Briefing Enhancer :8001"]
    CVS["Content Validation :8004"]

    LEGAL["Legal Service :8005"]
    HTML["HTML Converter :8011"]
    BRAND["Branding :8012"]

    LLM["Maritaca AI / OpenAI / Cohere"]

    FE -->|HTTP + JWT| GW

    GW -->|REST| AUTH
    GW -->|REST| CAMP
    GW -->|REST| BRIEF
    GW -->|REST| CVS

    CVS -->|MCP| CAMP
    CVS -->|A2A| LEGAL
    CVS -->|MCP| HTML
    CVS -->|MCP| BRAND

    BRIEF -->|LLM| LLM
    LEGAL -->|LLM| LLM

    LEGAL -->|RAG| WEAV[("Weaviate :8080")]

    subgraph DADOS["Infraestrutura"]
        direction LR
        PG[("PostgreSQL :5432")]
        REDIS["Redis :6379"]
        WEAV
        S3["LocalStack S3 :4566"]
    end

    subgraph OBS["Observabilidade"]
        direction LR
        GRAF["Grafana :3001"]
        META["Metabase :3002"]
        PROM["Prometheus :9090"]
    end

    style FE fill:#61dafb,color:#000
    style GW fill:#009485,color:#fff
    style AUTH fill:#ff6b6b,color:#fff
    style CAMP fill:#4ecdc4,color:#000
    style BRIEF fill:#95e1d3,color:#000
    style CVS fill:#f38181,color:#fff
    style LEGAL fill:#a29bfe,color:#fff
    style HTML fill:#ffeaa7,color:#000
    style BRAND fill:#dfe6e9,color:#000
    style LLM fill:#fdcb6e,color:#000
    style PG fill:#336791,color:#fff
    style WEAV fill:#00b894,color:#fff
    style REDIS fill:#d63031,color:#fff
    style S3 fill:#ffd93d,color:#000
    style PROM fill:#e17055,color:#fff
    style GRAF fill:#636e72,color:#fff
    style META fill:#636e72,color:#fff
    style DADOS fill:none,stroke:#336791
    style OBS fill:none,stroke:#636e72
```

## Serviços

| Serviço | Porta | O que faz |
|---|---|---|
| **API Gateway** | 8000 | Proxy reverso com autenticação JWT e rate limiting |
| **Auth Service** | 8002 | Registro, login, tokens JWT (access + refresh) |
| **Campaigns Service** | 8003 | CRUD de campanhas, peças criativas, upload S3. Expõe MCP tools |
| **Briefing Enhancer** | 8001 | Aprimora objetivos de campanha via LLM (LangGraph) |
| **Content Validation** | 8004 | Orquestra validação de peças: formato, specs, branding (MCP) e compliance (A2A) |
| **Legal Service** | 8005 | Validação jurídica via RAG (Weaviate + LangGraph). Expõe A2A |
| **Branding Service** | 8012 | Validação determinística de marca (cores, fontes, logo). Expõe MCP tools |
| **HTML Converter** | 8011 | Converte HTML de email em imagem (Spring Boot). Expõe MCP tool |
| **Frontend** | 3000 | Interface React + TypeScript + Vite + Tailwind |

### Protocolos de comunicação

- **REST**: Gateway roteia para Auth, Campaigns, Briefing Enhancer e Content Validation
- **MCP (Model Context Protocol)**: Content Validation consome tools de Campaigns, Branding e HTML Converter
- **A2A (Agent-to-Agent Protocol)**: Content Validation envia peças ao Legal Service para parecer jurídico

## Pré-requisitos

- Docker e Docker Compose
- Chave da OpenAI (`OPENAI_API_KEY`)
- Recomendado: chave da Maritaca (`MARITACA_API_KEY`) para a configuração de LLM com melhor accuracy

## Execução

### 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas chaves. Apenas `OPENAI_API_KEY` é obrigatória. Veja `.env.example` para detalhes sobre cada variável.

### 2. Subir os serviços

```bash
docker compose up -d
```

Isso inicia todos os containers, executa as migrations (Alembic) e carrega os dados pré-processados no Weaviate.

### 3. Acessar

| Recurso | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API Gateway (Swagger) | http://localhost:8000/docs |
| Grafana | http://localhost:3001 (admin / orqestra) |
| Metabase | http://localhost:3002 |
| Prometheus | http://localhost:9090 |

### Usuário padrão

O seed cria um usuário para testes:

```
Email: ana@email.com
Senha: 123
```

## Infraestrutura

| Componente | Porta | Uso |
|---|---|---|
| PostgreSQL | 5432 | Banco principal (um database por serviço) |
| Redis | 6379 | Cache de validações e enhancements (DB 0, 1, 2) |
| Weaviate | 8080 | Vector database para RAG do Legal Service |
| LocalStack (S3) | 4566 | Armazenamento de peças criativas (email HTML, imagens app) |

## Comandos úteis

```bash
# Ver logs de um serviço
docker compose logs -f legal-service

# Parar tudo
docker compose down

# Parar e limpar volumes (reset completo)
docker compose down -v

# Rebuild de um serviço
docker compose build content-validation-service
docker compose up -d content-validation-service
```

## Estrutura do repositório

```
├── api-gateway/                  Proxy reverso (FastAPI)
├── auth-service/                 Autenticação JWT (FastAPI)
├── briefing-enhancer-service/    Aprimoramento de briefings (LangGraph)
├── campaigns-service/            Gestão de campanhas + MCP server (FastAPI)
├── content-validation-service/   Orquestrador de validação (LangGraph)
├── legal-service/                Validação jurídica RAG + A2A (LangGraph)
├── branding-service/             Validação de marca via MCP (FastAPI)
├── html-converter-service/       HTML para imagem + MCP (Spring Boot)
├── frontend/                     SPA React + TypeScript
├── documents-ingestion/          Pipeline de ingestão de PDFs no Weaviate
├── monitoring/                   Prometheus, Grafana, Metabase
├── postman-collections/          Collection Postman com todos os endpoints
├── docker-compose.yml            Orquestração de todos os serviços
└── .env.example                  Variáveis de ambiente necessárias
```
