# Diagrama da Solução Orqestra — Estado Atual

> **Nota:** O frontend (React SPA) não é detalhado neste documento. O foco é a arquitetura de backend, serviços de IA e infraestrutura.

## Arquitetura Geral

> O diagrama visual completo está disponível em `assets/arquitetura_orqestra.png`.

```mermaid
graph TD
    FE["Frontend React :3000<br/><i>TypeScript · Vite · Tailwind</i>"]
    GW["API Gateway :8000<br/><i>FastAPI · Python</i>"]

    AUTH["Auth :8002<br/><i>FastAPI · bcrypt</i>"]
    CAMP["Campaigns :8003<br/><i>FastAPI · MCP Server</i>"]
    BRIEF["Briefing Enhancer :8001<br/><i>FastAPI · LangGraph · LangChain</i>"]
    CVS["Content Validation :8004<br/><i>FastAPI · LangGraph</i>"]

    LEGAL["Legal Service :8005<br/><i>FastAPI · LangGraph · LangChain · RAG</i>"]
    HTML["HTML Converter :8011<br/><i>Spring Boot · Java · MCP Server</i>"]
    BRAND["Branding :8012<br/><i>FastAPI · MCP Server</i>"]

    LLM["Maritaca AI · OpenAI · Cohere"]

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

    subgraph DADOS["Infraestrutura de Dados"]
        direction LR
        PG[("PostgreSQL :5432<br/>6 databases")]
        REDIS["Redis :6379<br/>3 DBs"]
        WEAV
        S3["S3 :4566"]
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

**Conexões de dados** (omitidas do diagrama para clareza):
- **PostgreSQL** ← Auth, Campaigns, Briefing Enhancer, Content Validation, Legal Service, Metabase
- **Redis** ← Legal Service (DB 0), Content Validation (DB 1), Briefing Enhancer (DB 2)
- **S3** ← Campaigns (upload/download de peças)
- **Prometheus** ← coleta métricas de todos os serviços → Grafana

## Protocolos de Comunicacao

```mermaid
graph LR
    subgraph "REST — HTTP/JSON"
        R2[API Gateway] --> R3[Auth Service]
        R2 --> R4[Campaigns Service]
        R2 --> R5[Briefing Enhancer]
        R2 --> R6[Content Validation]
    end

    subgraph "MCP — Model Context Protocol"
        M1[Content Validation] -->|retrieve_piece_content<br/>get_channel_specs| M2[Campaigns MCP]
        M1 -->|convert_html_to_image| M3[HTML Converter MCP]
        M1 -->|validate_email_brand<br/>validate_image_brand<br/>get_brand_guidelines| M4[Branding MCP]
    end

    subgraph "A2A — Agent-to-Agent"
        A1[Content Validation] -->|VALIDATE_COMMUNICATION| A2[Legal Service]
    end
```

## Fluxo de Validacao de Conteudo

```mermaid
sequenceDiagram
    participant GW as API Gateway
    participant CVS as Content Validation
    participant REDIS as Redis (cache)
    participant CAMP_MCP as Campaigns (MCP)
    participant HTML_MCP as HTML Converter (MCP)
    participant BRAND_MCP as Branding (MCP)
    participant LEGAL as Legal Service (A2A)
    participant WEAV as Weaviate

    GW->>CVS: POST /ai/analyze-piece

    CVS->>REDIS: verificar cache (content_hash)
    alt Cache hit
        REDIS-->>CVS: resultado em cache
        CVS-->>GW: resultado consolidado
    end

    par Buscar conteudo e specs
        CVS->>CAMP_MCP: retrieve_piece_content
        CAMP_MCP-->>CVS: conteudo da peca
        CVS->>CAMP_MCP: get_channel_specs
        CAMP_MCP-->>CVS: specs do canal
    end

    alt Canal EMAIL
        CVS->>HTML_MCP: convert_html_to_image
        HTML_MCP-->>CVS: imagem Base64
    end

    CVS->>CVS: validate_specs (deterministico)

    par Validacoes em paralelo
        CVS->>BRAND_MCP: validate_email_brand / validate_image_brand
        BRAND_MCP-->>CVS: resultado branding
        CVS->>LEGAL: A2A VALIDATE_COMMUNICATION
        LEGAL->>WEAV: hybrid search (RAG)
        WEAV-->>LEGAL: chunks regulatorios
        LEGAL->>LEGAL: LLM analisa conformidade
        LEGAL-->>CVS: APROVADO / REPROVADO
    end

    CVS->>CVS: issue_final_verdict (agrega resultados)
    CVS->>REDIS: salvar em cache (TTL 24h)
    CVS->>CVS: salvar auditoria (PostgreSQL)
    CVS-->>GW: resultado consolidado
```

## Fluxo de Autenticacao

```mermaid
sequenceDiagram
    participant GW as API Gateway
    participant AUTH as Auth Service
    participant DB as PostgreSQL

    GW->>AUTH: POST /api/auth/login
    AUTH->>DB: validar credenciais
    DB-->>AUTH: user data
    AUTH->>AUTH: gerar JWT (access + refresh)
    AUTH-->>GW: tokens + Set-Cookie (httpOnly)

    Note over GW,AUTH: Requisicoes seguintes
    GW->>GW: validar JWT localmente
    GW->>GW: injetar headers X-User-*
    GW->>GW: proxy para servico destino
```

## Fluxo de Aprimoramento de Briefing

```mermaid
sequenceDiagram
    participant GW as API Gateway
    participant BRIEF as Briefing Enhancer
    participant REDIS as Redis (cache)
    participant DB as PostgreSQL
    participant LLM as Maritaca / OpenAI

    GW->>BRIEF: POST /api/enhance-objective

    BRIEF->>REDIS: verificar cache
    alt Cache hit
        REDIS-->>BRIEF: texto aprimorado em cache
        BRIEF-->>GW: texto original + aprimorado
    end

    BRIEF->>DB: buscar field_info (diretrizes)
    DB-->>BRIEF: metadados do campo

    BRIEF->>LLM: sabiazinho-4 (principal)
    alt Fallback
        BRIEF->>LLM: gpt-5-nano (se Maritaca indisponivel)
    end
    LLM-->>BRIEF: texto aprimorado

    BRIEF->>REDIS: salvar em cache (TTL 24h)
    BRIEF->>DB: salvar ai_interaction (auditoria)
    BRIEF-->>GW: texto original + aprimorado
```

## Fluxo de Ciclo de Vida da Campanha

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Analista de Negocios cria
    DRAFT --> CREATIVE_STAGE: Analista de Negocios envia para criacao
    CREATIVE_STAGE --> CONTENT_REVIEW: Analista de Criacao submete pecas
    CONTENT_REVIEW --> CONTENT_ADJUSTMENT: Gestor de Marketing rejeita peca
    CONTENT_ADJUSTMENT --> CONTENT_REVIEW: Analista de Criacao resubmete
    CONTENT_REVIEW --> CAMPAIGN_BUILDING: Gestor de Marketing aprova todas
    CAMPAIGN_BUILDING --> CAMPAIGN_PUBLISHED: Analista de Campanhas publica
    CAMPAIGN_PUBLISHED --> [*]
```

## Bancos de Dados

```mermaid
erDiagram
    auth_service {
        users PK
        refresh_tokens FK
        login_audits FK
    }
    campaigns_service {
        campaigns PK
        comments FK
        creative_pieces FK
        piece_review FK
        piece_review_event FK
        campaign_status_event FK
        channel_specs PK
    }
    briefing_enhancer {
        enhanceable_fields PK
        ai_interactions FK
    }
    content_validation {
        piece_validation_audit PK
    }
    legal_service {
        legal_validation_audits PK
    }
    metabase {
        metabase_internal string
    }
```

## Estrategia de Cache (Redis)

| Servico | Redis DB | TTL | Chave | Proposito |
|---------|----------|-----|-------|-----------|
| Legal Service | DB 0 | 1h | `legal:{channel}:{content_hash}` | Cache de validacoes regulatorias |
| Content Validation | DB 1 | 24h | `validation:{campaign_id}:{channel}:{content_hash}` | Cache de resultados completos de validacao |
| Briefing Enhancer | DB 2 | 24h | `enhancement:{user}:{field}:{text_hash}` | Cache de textos aprimorados |

Todos os servicos mantêm registros permanentes de auditoria em PostgreSQL, independente do cache Redis.

## Mapa de Portas

| Servico | Porta | Protocolo | Descricao |
|---------|-------|-----------|-----------|
| API Gateway | 8000 | REST | Roteamento + JWT + Rate Limit |
| Briefing Enhancer | 8001 | REST | Aprimoramento de briefing com IA |
| Auth Service | 8002 | REST | Autenticacao e autorizacao |
| Campaigns Service | 8003 | REST + MCP | Gestao de campanhas e pecas |
| Content Validation | 8004 | REST + A2A | Orquestracao de validacao (LangGraph) |
| Legal Service | 8005 | REST + A2A | Validacao regulatoria (RAG) |
| HTML Converter | 8011 | MCP | Conversao HTML para imagem (Java) |
| Branding Service | 8012 | MCP | Validacao de marca (deterministico) |
| PostgreSQL | 5432 | SQL | 6 databases (auth, campaigns, briefing, content-validation, legal, metabase) |
| LocalStack S3 | 4566 | S3 API | Armazenamento de arquivos (email HTML, imagens app) |
| Weaviate | 8080 / 50051 | HTTP / gRPC | Base vetorial — documentos regulatorios |
| Redis | 6379 | Redis | Cache — DB 0 (Legal), DB 1 (Content Validation), DB 2 (Briefing Enhancer) |
| Prometheus | 9090 | HTTP | Coleta de metricas |
| Grafana | 3001 | HTTP | Dashboards tecnicos |
| Metabase | 3002 | HTTP | Dashboards de negocio |

## Comunicacao Entre Servicos

| Origem | Destino | Protocolo | Proposito |
|--------|---------|-----------|-----------|
| API Gateway | Auth Service | REST | Roteamento /api/auth/* |
| API Gateway | Campaigns Service | REST | Roteamento /api/campaigns/* |
| API Gateway | Briefing Enhancer | REST | Roteamento /api/enhance-objective, /api/ai-interactions |
| API Gateway | Content Validation | REST | Roteamento /api/ai/analyze-piece |
| Campaigns Service | Auth Service | REST | Validacao de token |
| Briefing Enhancer | Auth Service | REST | Validacao de token |
| Content Validation | Auth Service | REST | Validacao de token |
| Content Validation | Campaigns Service | MCP | retrieve_piece_content, get_channel_specs |
| Content Validation | HTML Converter | MCP | convert_html_to_image |
| Content Validation | Branding Service | MCP | validate_email_brand, validate_image_brand, get_brand_guidelines |
| Content Validation | Legal Service | A2A | VALIDATE_COMMUNICATION |
| Legal Service | Weaviate | HTTP/gRPC | Hybrid search (RAG — chunking semantico) |
| Legal Service | Redis | Redis | Cache de validacoes (DB 0, TTL 1h) |
| Content Validation | Redis | Redis | Cache de resultados (DB 1, TTL 24h) |
| Briefing Enhancer | Redis | Redis | Cache de aprimoramentos (DB 2, TTL 24h) |
| Campaigns Service | LocalStack S3 | S3 API | Upload/download de arquivos |

## LLMs e APIs Externas

| Servico | Provedor | Modelo | Uso |
|---------|----------|--------|-----|
| Briefing Enhancer | Maritaca AI | sabiazinho-4 | Aprimoramento de texto (principal) |
| Briefing Enhancer | OpenAI | gpt-5-nano | Aprimoramento de texto (fallback) |
| Legal Service | Maritaca AI | sabiazinho-4 | Validacao regulatoria SMS/PUSH |
| Legal Service | OpenAI | gpt-5-nano | Validacao regulatoria EMAIL/APP (com imagem) |
| Legal Service | OpenAI | text-embedding-3-small | Embeddings para RAG |
| Legal Service | Cohere | Rerank v3 | Reranking (desabilitado — degradou recall nos experimentos) |

> **Nota:** O Content Validation Service nao invoca LLMs diretamente. Ele orquestra chamadas a servicos especializados (Legal, Branding, HTML Converter, Campaigns) via LangGraph.

## Perfis de Usuario

| Perfil | Permissoes |
|--------|-----------|
| Analista de Negocios | Cria campanhas, edita briefing, movimenta status, visualiza |
| Analista de Criacao | Submete pecas criativas, solicita validacao IA, submete para revisao |
| Analista de Campanhas | Visualiza campanhas, faz download de pecas |
| Gestor de Marketing | Aprova/rejeita pecas, solicita validacao IA adicional, veredito final |

## Tecnologias

- **Backend**: FastAPI (Python 3.11+), Spring Boot (Java — HTML Converter)
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS (detalhamento fora deste documento)
- **IA/ML**: LangGraph, LangChain, OpenAI API, Maritaca AI API
- **Banco de Dados**: PostgreSQL 16 (6 databases)
- **Vetorial**: Weaviate 1.29 (hybrid search, embeddings OpenAI, chunking semantico)
- **Cache**: Redis 7 (3 databases isolados por servico)
- **Storage**: LocalStack S3
- **Observabilidade**: Prometheus, Grafana (tecnico), Metabase (negocio)
- **Orquestracao**: Docker Compose
- **Autenticacao**: JWT (httpOnly cookies)
- **Protocolos**: REST, MCP (Model Context Protocol), A2A (Agent-to-Agent)

---

## Arquitetura de Producao (AWS)

```mermaid
graph TD
    subgraph L1["Internet"]
        USER["Usuarios"]
    end

    subgraph L2["Servicos Globais AWS — fora da VPC"]
        direction LR
        R53["Route 53<br/>DNS"]
        CF["CloudFront<br/>CDN Global"]
        WAF["WAF<br/>Firewall"]
        S3FE["S3<br/>Frontend"]
    end

    subgraph L2B["Servicos Gerenciados AWS — fora da VPC"]
        direction LR
        CW["CloudWatch<br/>Logs e Metricas"]
        AMG["Managed<br/>Grafana"]
        SM["Secrets<br/>Manager"]
        ECR["ECR<br/>Imagens Docker"]
    end

    subgraph VPC["VPC"]

        subgraph L3["Sub-rede Publica"]
            ALB["Application Load Balancer"]
            NATGW["NAT Gateway"]
        end

        subgraph PRIV["Sub-rede Privada"]

            subgraph ECS["ECS Fargate"]
                direction LR
                GW_F["API Gateway"]
                AUTH_F["Auth"]
                CAMP_F["Campaigns"]
                BRIEF_F["Briefing<br/>Enhancer"]
            end

            subgraph ECS2["ECS Fargate"]
                direction LR
                CVS_F["Content<br/>Validation"]
                LEGAL_F["Legal<br/>Service"]
                HTML_F["HTML<br/>Converter"]
                BRAND_F["Branding"]
            end

            subgraph ECS3["ECS Fargate"]
                META_F["Metabase"]
            end

        end

        subgraph DADOS["Sub-rede de Dados"]
            direction LR
            RDS[("RDS PostgreSQL<br/>Multi-AZ")]
            ELASTI["ElastiCache<br/>Redis"]
            WEAV_F["Weaviate<br/>ECS"]
            S3B["S3<br/>Pecas Criativas"]
        end

    end

    subgraph L6["APIs Externas — internet"]
        direction LR
        MARITACA["Maritaca AI"]
        OPENAI["OpenAI"]
        COHERE["Cohere"]
    end

    USER -->|HTTPS| R53
    R53 --> CF
    CF --> WAF
    CF -.->|static assets| S3FE
    WAF --> ALB

    ALB --> GW_F
    GW_F --> AUTH_F
    GW_F --> CAMP_F
    GW_F --> BRIEF_F
    GW_F --> CVS_F

    CVS_F -->|MCP| CAMP_F
    CVS_F -->|MCP| HTML_F
    CVS_F -->|MCP| BRAND_F
    CVS_F -->|A2A| LEGAL_F

    ECS -->|NAT Gateway| MARITACA
    ECS2 -->|NAT Gateway| OPENAI
    ECS2 -.->|NAT Gateway| COHERE

    AUTH_F --> RDS
    CAMP_F --> RDS
    BRIEF_F --> RDS
    CVS_F --> RDS
    LEGAL_F --> RDS
    META_F --> RDS

    LEGAL_F --> ELASTI
    CVS_F --> ELASTI
    BRIEF_F --> ELASTI

    LEGAL_F --> WEAV_F
    CAMP_F --> S3B

    CW -.->|metricas| ECS
    CW -.->|metricas| ECS2
    AMG -.-> CW

    style L1 fill:none,stroke:#636e72
    style L2 fill:none,stroke:#ff9900
    style L2B fill:none,stroke:#ff9900
    style VPC fill:none,stroke:#232f3e
    style L3 fill:none,stroke:#4ecdc4
    style PRIV fill:none,stroke:#f38181
    style ECS fill:none,stroke:#f38181
    style ECS2 fill:none,stroke:#a29bfe
    style ECS3 fill:none,stroke:#636e72
    style L6 fill:none,stroke:#fdcb6e
    style DADOS fill:none,stroke:#336791
    style NATGW fill:#4ecdc4,color:#000
    style ALB fill:#4ecdc4,color:#000
    style GW_F fill:#009485,color:#fff
    style AUTH_F fill:#ff6b6b,color:#fff
    style CAMP_F fill:#4ecdc4,color:#000
    style BRIEF_F fill:#95e1d3,color:#000
    style CVS_F fill:#f38181,color:#fff
    style LEGAL_F fill:#a29bfe,color:#fff
    style HTML_F fill:#ffeaa7,color:#000
    style BRAND_F fill:#dfe6e9,color:#000
    style META_F fill:#636e72,color:#fff
    style RDS fill:#336791,color:#fff
    style ELASTI fill:#d63031,color:#fff
    style WEAV_F fill:#00b894,color:#fff
    style S3B fill:#ffd93d,color:#000
    style S3FE fill:#ffd93d,color:#000
    style R53 fill:#ff9900,color:#000
    style CF fill:#ff9900,color:#000
    style WAF fill:#ff9900,color:#000
    style SM fill:#ff9900,color:#000
    style ECR fill:#ff9900,color:#000
    style CW fill:#ff9900,color:#000
    style AMG fill:#ff9900,color:#000
```

### Decisoes de Arquitetura AWS

| Componente Local | Equivalente AWS | Justificativa |
|-----------------|----------------|---------------|
| Docker Compose | **ECS Fargate** | Serverless containers, sem gerenciar EC2 |
| PostgreSQL (container) | **RDS PostgreSQL Multi-AZ** | Alta disponibilidade, backups automaticos |
| Redis (container) | **ElastiCache Redis** | Gerenciado, replicacao automatica |
| LocalStack S3 | **S3** | Servico nativo, sem mudanca de codigo |
| Weaviate (container) | **Weaviate em ECS ou EC2** | Sem equivalente gerenciado AWS; EC2 com EBS para persistencia |
| Frontend (container Vite) | **S3 + CloudFront** | SPA servida como static assets via CDN |
| Prometheus + Grafana | **CloudWatch + Amazon Managed Grafana** | Gerenciados, sem manutencao |
| Metabase (container) | **Metabase em ECS Fargate** | Mantem a ferramenta, mas gerenciado |
| `.env` files | **Secrets Manager** | Rotacao automatica de segredos, auditoria |
| Rede Docker default | **VPC com sub-redes publica/privada** | Segregacao real de rede |
| — | **WAF** | Protecao contra ataques web (OWASP top 10) |
| — | **Route 53 + CloudFront** | DNS gerenciado + CDN + HTTPS automatico |
| — | **ECR** | Registro privado de imagens Docker |

### Seguranca de Rede

```
Internet
  |
  v
+-----------------------------+
|  Sub-rede Publica           |
|  - ALB (porta 443)          |
|  - NAT Gateway (saida)      |
+----------+------------------+
           | Security Group: apenas ALB -> ECS
           v
+-----------------------------+
|  Sub-rede Privada           |
|  - ECS Fargate (servicos)   |
|  - Sem IP publico           |
|  - Saida via NAT Gateway    |
+----------+------------------+
           | Security Group: apenas ECS -> Data
           v
+-----------------------------+
|  Sub-rede de Dados          |
|  - RDS PostgreSQL           |
|  - ElastiCache Redis        |
|  - Weaviate (EC2/ECS)       |
|  - Sem acesso a internet    |
+-----------------------------+
```
