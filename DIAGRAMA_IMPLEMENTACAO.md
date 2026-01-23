# Diagrama da Solução - Estado Atual da Implementação

## Arquitetura de Microsserviços

```mermaid
graph TB
    subgraph "Frontend"
        FE[React SPA<br/>Port: 3000<br/>React Router 6]
        FE_PAGES[Páginas:<br/>- Login<br/>- Register<br/>- Index<br/>- Campaigns<br/>- CampaignDetail<br/>- CampaignNew<br/>- Settings]
        FE --> FE_PAGES
    end

    subgraph "API Gateway"
        GW[FastAPI Gateway<br/>Port: 8000<br/>Proxy/Roteamento]
    end

    subgraph "Microsserviços"
        subgraph "Auth Service"
            AUTH[FastAPI<br/>Port: 8002]
            AUTH_ROUTES[Endpoints:<br/>POST /register<br/>POST /login<br/>POST /refresh<br/>POST /logout<br/>GET /me<br/>GET /users/:id]
            AUTH_DB[(PostgreSQL<br/>auth_service)]
            AUTH_TABLES[Tables:<br/>- users<br/>- refresh_tokens<br/>- login_audits]
            AUTH --> AUTH_ROUTES
            AUTH --> AUTH_DB
            AUTH_DB --> AUTH_TABLES
        end

        subgraph "Campaigns Service"
            CAMP[FastAPI<br/>Port: 8003]
            CAMP_ROUTES[Endpoints:<br/>GET /campaigns<br/>GET /campaigns/:id<br/>POST /campaigns<br/>PUT /campaigns/:id<br/>DELETE /campaigns/:id<br/>POST /campaigns/:id/comments<br/>POST /campaigns/:id/creative-pieces<br/>POST /campaigns/:id/creative-pieces/upload-app<br/>POST /campaigns/:id/creative-pieces/upload-email<br/>DELETE /campaigns/:id/creative-pieces/app/:space<br/>DELETE /campaigns/:id/creative-pieces/email]
            CAMP_DB[(PostgreSQL<br/>campaigns_service)]
            CAMP_TABLES[Tables:<br/>- campaigns<br/>- comments<br/>- creative_pieces]
            CAMP --> CAMP_ROUTES
            CAMP --> CAMP_DB
            CAMP_DB --> CAMP_TABLES
        end

        subgraph "Briefing Enhancer Service"
            BRIEF[FastAPI + LangGraph<br/>Port: 8001]
            BRIEF_ROUTES[Endpoints:<br/>POST /enhance-objective<br/>PATCH /ai-interactions/:id/decision<br/>GET /health]
            BRIEF_DB[(PostgreSQL<br/>briefing_enhancer)]
            BRIEF_TABLES[Tables:<br/>- enhanceable_fields<br/>- ai_interactions]
            BRIEF_GRAPH[LangGraph Workflow:<br/>1. fetch_field_info<br/>2. enhance_text<br/>Checkpointing opcional]
            BRIEF_LLM[OpenAI Integration:<br/>- GPT-4o<br/>- Moderation Middleware<br/>- Config via YAML]
            BRIEF --> BRIEF_ROUTES
            BRIEF --> BRIEF_GRAPH
            BRIEF_GRAPH --> BRIEF_LLM
            BRIEF --> BRIEF_DB
            BRIEF_DB --> BRIEF_TABLES
        end

        subgraph "AI Studio Service"
            AI[FastAPI<br/>Port: 8004]
            AI_ROUTES[Endpoints:<br/>POST /ai/analyze-piece<br/>GET /ai/analyze-piece/:campaign_id/:channel]
            AI_DB[(PostgreSQL<br/>ai_studio)]
            AI_TABLES[Tables:<br/>- creative_piece_analysis]
            AI --> AI_ROUTES
            AI --> AI_DB
            AI_DB --> AI_TABLES
        end
    end

    subgraph "Infraestrutura"
        S3[LocalStack S3<br/>Port: 4566<br/>Bucket: orqestra-creative-pieces]
        PG[(PostgreSQL 16<br/>Port: 5432<br/>Múltiplos databases)]
    end

    FE -->|HTTP + JWT| GW
    GW -->|/api/auth/*| AUTH
    GW -->|/api/campaigns/*| CAMP
    GW -->|/api/enhance-objective<br/>/api/ai-interactions| BRIEF
    GW -->|/api/ai/analyze-piece<br/>/api/ai/generate-text| AI

    CAMP -->|Valida token| AUTH
    BRIEF -->|Valida token| AUTH
    AI -->|Valida token| AUTH
    CAMP -->|Upload/Download| S3
    CAMP -->|Busca campanha| CAMP_DB
    AI -->|Busca campanha| CAMP

    AUTH --> AUTH_DB
    CAMP --> CAMP_DB
    BRIEF --> BRIEF_DB
    AI --> AI_DB
    AUTH_DB --> PG
    CAMP_DB --> PG
    BRIEF_DB --> PG
    AI_DB --> PG

    style FE fill:#61dafb
    style GW fill:#009485
    style AUTH fill:#ff6b6b
    style CAMP fill:#4ecdc4
    style BRIEF fill:#95e1d3
    style AI fill:#f38181
    style S3 fill:#ffd93d
    style PG fill:#336791
```

## Fluxo de Autenticação

```mermaid
sequenceDiagram
    participant U as Usuário
    participant FE as Frontend
    participant GW as API Gateway
    participant AUTH as Auth Service
    participant DB as PostgreSQL

    U->>FE: Login (email + password)
    FE->>GW: POST /api/auth/login
    GW->>AUTH: POST /login (proxy)
    AUTH->>DB: Validar credenciais
    DB-->>AUTH: User data
    AUTH->>AUTH: Gerar JWT tokens
    AUTH->>AUTH: Set httpOnly cookies
    AUTH-->>GW: TokenResponse + Set-Cookie
    GW-->>FE: TokenResponse + Set-Cookie
    FE->>FE: Armazenar tokens (cookies)
    
    Note over FE,GW: Próximas requisições
    U->>FE: Ação protegida
    FE->>GW: Request + Cookie (access_token)
    GW->>AUTH: GET /me (validação)
    AUTH->>DB: Verificar token
    DB-->>AUTH: User válido
    AUTH-->>GW: User data
    GW->>GW: Proxy para serviço destino
```

## Fluxo de Criação de Campanha

```mermaid
sequenceDiagram
    participant U as Business Analyst
    participant FE as Frontend
    participant GW as API Gateway
    participant CAMP as Campaigns Service
    participant AUTH as Auth Service
    participant DB as PostgreSQL

    U->>FE: Criar nova campanha
    FE->>GW: POST /api/campaigns (com dados)
    GW->>CAMP: POST /campaigns (proxy)
    CAMP->>AUTH: GET /me (validar token)
    AUTH-->>CAMP: User data (role)
    CAMP->>CAMP: Verificar role = Business Analyst
    CAMP->>DB: INSERT campaign
    DB-->>CAMP: Campaign criada
    CAMP-->>GW: CampaignResponse
    GW-->>FE: CampaignResponse
    FE->>FE: Atualizar lista
```

## Fluxo de Aprimoramento de Texto (Briefing Enhancer)

```mermaid
sequenceDiagram
    participant U as Business Analyst
    participant FE as Frontend
    participant GW as API Gateway
    participant BRIEF as Briefing Enhancer
    participant AUTH as Auth Service
    participant GRAPH as LangGraph
    participant LLM as OpenAI
    participant DB as PostgreSQL

    U->>FE: Aprimorar objetivo
    FE->>GW: POST /api/enhance-objective
    GW->>BRIEF: POST /enhance-objective (proxy)
    BRIEF->>AUTH: GET /me (validar token)
    AUTH-->>BRIEF: User data (role)
    BRIEF->>BRIEF: Verificar role = Business Analyst
    BRIEF->>GRAPH: Executar workflow
    GRAPH->>DB: Buscar field_info
    DB-->>GRAPH: Field metadata
    GRAPH->>LLM: Chamar OpenAI (GPT-4o)
    LLM->>LLM: Moderation check
    LLM-->>GRAPH: Texto aprimorado
    GRAPH->>DB: Salvar interação
    GRAPH-->>BRIEF: EnhancedTextResponse
    BRIEF-->>GW: Response
    GW-->>FE: Response
    FE->>FE: Exibir texto aprimorado
```

## Fluxo de Upload de Peça Criativa

```mermaid
sequenceDiagram
    participant U as Creative Analyst
    participant FE as Frontend
    participant GW as API Gateway
    participant CAMP as Campaigns Service
    participant AUTH as Auth Service
    participant S3 as LocalStack S3
    participant DB as PostgreSQL

    U->>FE: Upload arquivo App/E-mail
    FE->>GW: POST /api/campaigns/:id/creative-pieces/upload-app
    GW->>CAMP: POST /campaigns/:id/creative-pieces/upload-app
    CAMP->>AUTH: GET /me (validar token)
    AUTH-->>CAMP: User data (role)
    CAMP->>CAMP: Verificar role = Creative Analyst
    CAMP->>CAMP: Verificar status campanha
    CAMP->>S3: Upload arquivo
    S3-->>CAMP: File URL
    CAMP->>DB: INSERT/UPDATE creative_piece
    DB-->>CAMP: CreativePiece salvo
    CAMP-->>GW: CreativePieceResponse
    GW-->>FE: Response com URL pública
    FE->>FE: Exibir preview
```

## Fluxo de Análise de Peça Criativa (AI Studio)

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant GW as API Gateway
    participant AI as AI Studio Service
    participant AUTH as Auth Service
    participant CAMP as Campaigns Service
    participant DB as PostgreSQL

    U->>FE: Analisar peça SMS/Push
    FE->>GW: POST /api/ai/analyze-piece
    GW->>AI: POST /ai/analyze-piece
    AI->>AUTH: GET /me (validar token)
    AUTH-->>AI: User data
    AI->>AI: Calcular hash do conteúdo
    AI->>DB: Verificar análise existente
    alt Análise já existe
        DB-->>AI: Análise existente
    else Nova análise
        AI->>CAMP: GET /campaigns/:id
        CAMP-->>AI: Campaign data
        AI->>AI: Validar contra briefing
        AI->>DB: INSERT creative_piece_analysis
        DB-->>AI: Análise criada
    end
    AI-->>GW: AnalyzePieceResponse
    GW-->>FE: Response
    FE->>FE: Exibir validação
```

## Componentes Implementados

### Frontend (React)
- ✅ Sistema de roteamento (React Router 6)
- ✅ Páginas: Login, Register, Index, Campaigns, CampaignDetail, CampaignNew, Settings
- ✅ Proteção de rotas (ProtectedRoute)
- ✅ Integração com API Gateway
- ✅ UI Components (Radix UI + TailwindCSS)

### API Gateway
- ✅ Roteamento baseado em path
- ✅ Proxy transparente de requisições
- ✅ Repasse de headers de autenticação
- ✅ Repasse de cookies (Set-Cookie)
- ✅ Tratamento de erros e timeouts

### Auth Service
- ✅ Registro de usuários
- ✅ Login com JWT
- ✅ Refresh tokens
- ✅ Logout
- ✅ Validação de tokens (/me)
- ✅ Rate limiting
- ✅ Auditoria de login
- ✅ Cookies httpOnly

### Campaigns Service
- ✅ CRUD completo de campanhas
- ✅ Sistema de comentários
- ✅ Gerenciamento de peças criativas (App e E-mail)
- ✅ Upload de arquivos para S3
- ✅ Validação de permissões por role
- ✅ Workflow de status de campanha
- ✅ Integração com Auth Service

### Briefing Enhancer Service
- ✅ Aprimoramento de texto usando LangGraph
- ✅ Integração com OpenAI (GPT-4o)
- ✅ Moderation middleware
- ✅ Checkpointing opcional (LangSmith)
- ✅ Histórico de interações
- ✅ Decisões do usuário (approved/rejected)
- ✅ Configuração via YAML

### AI Studio Service
- ✅ Análise de peças criativas (SMS e Push)
- ✅ Validação contra briefing
- ✅ Cache por hash de conteúdo
- ✅ Integração com Campaigns Service
- ✅ Análise de validação (valid/invalid/warning)

### Infraestrutura
- ✅ PostgreSQL 16 (múltiplos databases)
- ✅ LocalStack S3 (armazenamento de arquivos)
- ✅ Docker Compose (orquestração)
- ✅ Health checks

## Comunicação Entre Serviços

| Origem | Destino | Propósito | Protocolo |
|--------|---------|-----------|-----------|
| Frontend | API Gateway | Todas as requisições | HTTP + JWT (cookies) |
| API Gateway | Auth Service | Roteamento /api/auth/* | HTTP |
| API Gateway | Campaigns Service | Roteamento /api/campaigns/* | HTTP |
| API Gateway | Briefing Enhancer | Roteamento /api/enhance-objective | HTTP |
| API Gateway | AI Studio | Roteamento /api/ai/* | HTTP |
| Campaigns Service | Auth Service | Validação de token | HTTP |
| Briefing Enhancer | Auth Service | Validação de token | HTTP |
| AI Studio | Auth Service | Validação de token | HTTP |
| AI Studio | Campaigns Service | Buscar dados da campanha | HTTP |
| Campaigns Service | LocalStack S3 | Upload/Download arquivos | S3 API |

## Bancos de Dados

### auth_service
- `users` - Usuários do sistema
- `refresh_tokens` - Tokens de refresh
- `login_audits` - Auditoria de logins

### campaigns_service
- `campaigns` - Campanhas
- `comments` - Comentários nas campanhas
- `creative_pieces` - Peças criativas (App, E-mail, SMS, Push)

### briefing_enhancer
- `enhanceable_fields` - Campos aprimoráveis
- `ai_interactions` - Histórico de interações com IA

### ai_studio
- `creative_piece_analysis` - Análises de peças criativas

## Tecnologias Utilizadas

- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Radix UI
- **Backend**: FastAPI, Python 3.11+
- **IA**: LangGraph, LangChain, OpenAI API
- **Banco de Dados**: PostgreSQL 16
- **Storage**: LocalStack (S3)
- **Orquestração**: Docker Compose
- **Autenticação**: JWT, httpOnly cookies

