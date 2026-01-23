# Briefing Enhancer Service - Diagramas

## 1. Arquitetura e Fluxo do Serviço

```mermaid
graph TB
    subgraph "Frontend / API Gateway"
        Client[Cliente HTTP]
    end
    
    subgraph "Briefing Enhancer Service"
        subgraph "API Layer"
            Router[FastAPI Router<br/>/api/enhance-objective<br/>/api/ai-interactions/:id/decision]
            Auth[Auth Middleware<br/>get_current_user]
            Permissions[Permissions Check<br/>require_business_analyst]
        end
        
        subgraph "Service Layer"
            AIService[AIService<br/>enhance_objective<br/>update_interaction_decision]
            ThreadID[Thread ID Generator<br/>session_id > campaign_id]
        end
        
        subgraph "Graph Layer - LangGraph"
            Graph[Enhancement Graph<br/>StateGraph]
            Node1[fetch_field_info Node]
            Node2[enhance_text Node]
            Checkpointer[PostgreSQL Checkpointer<br/>AsyncPostgresSaver]
        end
        
        subgraph "LLM Integration"
            Agent[LangChain Agent<br/>create_agent]
            ChatOpenAI[ChatOpenAI<br/>gpt-5-nano-2025-08-07]
            Moderation[OpenAIModerationMiddleware<br/>omni-moderation-latest]
            StructuredOutput[EnhancedTextResponse<br/>Pydantic Schema]
        end
        
        subgraph "Data Layer"
            DB[(PostgreSQL<br/>briefing_enhancer)]
            EnhanceableField[EnhanceableField Model<br/>enhanceable_fields table]
            AIInteraction[AIInteraction Model<br/>audit_interactions table]
            CheckpointsTable[checkpoints table<br/>LangGraph state]
        end
        
        subgraph "External Services"
            AuthService[Auth Service<br/>User validation]
            LangSmith[LangSmith<br/>Tracing]
        end
        
        subgraph "Configuration"
            ConfigYAML[config/models.yaml<br/>Model settings]
        end
    end
    
    Client -->|POST /api/enhance-objective| Router
    Router --> Auth
    Auth -->|Validate token| AuthService
    Auth --> Permissions
    Permissions --> AIService
    
    AIService -->|Generate thread_id| ThreadID
    AIService -->|Run graph| Graph
    Graph -->|Node 1| Node1
    Node1 -->|Query| EnhanceableField
    EnhanceableField --> DB
    Node1 -->|Return state| Graph
    Graph -->|Node 2| Node2
    Node2 -->|Build prompt| Agent
    Agent --> ChatOpenAI
    ChatOpenAI --> Moderation
    Moderation --> StructuredOutput
    StructuredOutput -->|Result| Node2
    Node2 -->|Update history| Graph
    Graph -->|Save state| Checkpointer
    Checkpointer --> CheckpointsTable
    CheckpointsTable --> DB
    
    AIService -->|Log interaction| AIInteraction
    AIInteraction --> DB
    
    Graph -.->|Trace| LangSmith
    Agent -.->|Trace| LangSmith
    
    ConfigYAML -->|Load config| Graph
    ConfigYAML -->|Model settings| ChatOpenAI
    
    AIService -->|Return| Router
    Router -->|Response| Client
```

## 2. Fluxo de Execução Detalhado

```mermaid
sequenceDiagram
    participant Client
    participant Router
    participant AIService
    participant Graph
    participant Node1 as fetch_field_info
    participant Node2 as enhance_text
    participant LLM as OpenAI LLM
    participant DB as PostgreSQL
    participant Checkpointer
    
    Client->>Router: POST /api/enhance-objective<br/>{text, field_name, campaign_id, session_id}
    Router->>Router: Validate auth & permissions
    Router->>AIService: enhance_objective(request_data, db, user_id)
    
    AIService->>AIService: Generate thread_id<br/>(session_id > campaign_id)
    AIService->>Graph: run_enhancement_graph(<br/>field_name, text, thread_id)
    
    Graph->>Graph: Load config from models.yaml
    Graph->>Graph: Create ChatOpenAI agent<br/>with moderation middleware
    Graph->>Checkpointer: get_checkpoint_saver()<br/>(if thread_id exists)
    Checkpointer->>DB: Setup checkpoints table<br/>(if not exists)
    Graph->>Graph: create_enhancement_graph(agent, checkpointer)
    
    Graph->>Node1: fetch_field_info(state, db)
    Node1->>DB: Query enhanceable_fields<br/>WHERE field_name = ?
    DB-->>Node1: Field info or default
    Node1->>Node1: Build previous_fields_summary<br/>from enhancement_history
    Node1-->>Graph: {field_info, previous_summary, history}
    
    Graph->>Node2: enhance_text(state, structured_llm)
    Node2->>Node2: build_enhancement_prompt(<br/>field_info, text, history)
    Node2->>LLM: invoke({system, user messages})
    LLM->>LLM: Moderation check (input)
    LLM->>LLM: Generate enhanced text
    LLM->>LLM: Moderation check (output)
    LLM-->>Node2: EnhancedTextResponse<br/>{enhanced_text, explanation}
    
    alt Moderation Error
        LLM-->>Node2: OpenAIModerationError
        Node2-->>Graph: {enhanced_text: "", explanation: "rejeitado"}
    else Success
        Node2->>Node2: Create new_enhancement<br/>Add to history
        Node2-->>Graph: {enhanced_text, explanation, history}
    end
    
    Graph->>Checkpointer: Save state (if enabled)
    Checkpointer->>DB: INSERT/UPDATE checkpoints<br/>WHERE thread_id = ?
    
    Graph-->>AIService: {enhanced_text, explanation}
    AIService->>DB: INSERT audit_interactions<br/>(log interaction)
    AIService-->>Router: EnhanceObjectiveResponse<br/>{enhanced_text, explanation, interaction_id}
    Router-->>Client: 200 OK
```

## 3. Estrutura de Componentes

```mermaid
graph LR
    subgraph "app/"
        subgraph "api/"
            Routes[routes.py<br/>FastAPI endpoints]
            Services[services.py<br/>AIService class]
            Schemas[schemas.py<br/>Pydantic models]
        end
        
        subgraph "graph/"
            GraphFile[graph.py<br/>LangGraph workflow]
            Nodes[nodes.py<br/>Graph nodes]
            State[state.py<br/>TypedDict state]
            Prompts[prompts.py<br/>Prompt builders]
            GraphSchemas[schemas.py<br/>EnhancedTextResponse]
        end
        
        subgraph "models/"
            EnhanceableField[enhanceable_field.py<br/>EnhanceableField]
            AIInteraction[ai_interaction.py<br/>AIInteraction]
        end
        
        subgraph "core/"
            Config[config.py<br/>Settings]
            Database[database.py<br/>SQLAlchemy Base]
            AuthClient[auth_client.py<br/>Auth validation]
            Checkpointer[checkpointer.py<br/>PostgreSQL checkpointer]
            Permissions[permissions.py<br/>Role checks]
        end
    end
    
    subgraph "config/"
        ModelsYAML[models.yaml<br/>LLM configuration]
    end
    
    Routes --> Services
    Routes --> Schemas
    Routes --> AuthClient
    Routes --> Permissions
    
    Services --> GraphFile
    Services --> AIInteraction
    
    GraphFile --> Nodes
    GraphFile --> State
    GraphFile --> Checkpointer
    GraphFile --> ModelsYAML
    
    Nodes --> EnhanceableField
    Nodes --> Prompts
    Nodes --> GraphSchemas
    
    EnhanceableField --> Database
    AIInteraction --> Database
    
    Checkpointer --> Database
```

## 4. Diagrama de Banco de Dados (ER)

```mermaid
erDiagram
    enhanceable_fields {
        string field_name PK "Primary Key"
        string display_name "NOT NULL"
        text expectations "NOT NULL"
        text improvement_guidelines "NULLABLE"
        timestamp created_at "NOT NULL, DEFAULT now()"
        timestamp updated_at "NOT NULL, DEFAULT now()"
    }
    
    audit_interactions {
        string id PK "UUID, Primary Key"
        string user_id "NOT NULL, Indexed"
        string campaign_id "NULLABLE, Indexed"
        string field_name "NOT NULL, Indexed"
        text input_text "NOT NULL"
        text output_text "NOT NULL"
        text explanation "NOT NULL"
        string session_id "NULLABLE, Indexed"
        string user_decision "NULLABLE, Indexed<br/>'approved' | 'rejected'"
        timestamp decision_at "NULLABLE"
        timestamp created_at "NOT NULL, DEFAULT now()"
    }
    
    checkpoints {
        thread_id string "Part of PK"
        checkpoint_ns string "Part of PK"
        checkpoint_id string "Part of PK"
        parent_checkpoint_id string "NULLABLE"
        checkpoint blob "JSON state"
        metadata jsonb "NULLABLE"
    }
    
    checkpoint_blobs {
        thread_id string "Part of PK"
        checkpoint_ns string "Part of PK"
        checkpoint_id string "Part of PK"
        channel string "Part of PK"
        version string "Part of PK"
        type string
        blob bytea
    }
    
    enhanceable_fields ||--o{ audit_interactions : "field_name references"
    
    note right of enhanceable_fields
        Campos configuráveis para aprimoramento:
        - businessObjective
        - expectedResult
        - targetAudienceDescription
        - exclusionCriteria
    end note
    
    note right of audit_interactions
        Audit log de todas as interações com IA.
        Permite rastrear:
        - Quem usou (user_id)
        - Quando (created_at)
        - Qual campo (field_name)
        - Input/Output
        - Decisão do usuário (approved/rejected)
    end note
    
    note right of checkpoints
        Tabelas criadas automaticamente
        pelo LangGraph para checkpointing.
        Armazena estado do grafo por thread_id.
    end note
```

## 5. Fluxo de Checkpointing

```mermaid
graph TD
    Start[Request com session_id ou campaign_id]
    Start --> GenerateThread[Generate thread_id<br/>session_id > campaign_id]
    GenerateThread --> CheckCheckpointer{Checkpointer<br/>initialized?}
    
    CheckCheckpointer -->|No| InitCheckpointer[Initialize AsyncPostgresSaver]
    InitCheckpointer --> CheckTables{Tables exist?}
    CheckTables -->|No| SetupTables[Run PostgresSaver.setup<br/>CREATE TABLE checkpoints<br/>CREATE INDEX CONCURRENTLY]
    SetupTables --> CreatePool[Create AsyncConnectionPool]
    CheckTables -->|Yes| CreatePool
    CreatePool --> CreateSaver[Create AsyncPostgresSaver]
    CreateSaver --> CompileGraph[Compile graph with checkpointer]
    
    CheckCheckpointer -->|Yes| CompileGraph
    
    CompileGraph --> InvokeGraph[Invoke graph with<br/>configurable: thread_id]
    
    InvokeGraph --> Node1[fetch_field_info]
    Node1 --> SaveState1[Save state to checkpoints<br/>thread_id = session_xxx]
    SaveState1 --> Node2[enhance_text]
    Node2 --> SaveState2[Update state in checkpoints]
    SaveState2 --> End[Return result]
    
    style CheckCheckpointer fill:#e1f5ff
    style CheckTables fill:#e1f5ff
    style SaveState1 fill:#fff4e1
    style SaveState2 fill:#fff4e1
```

## 6. Tratamento de Erros

```mermaid
graph TD
    Start[enhance_text node]
    Start --> InvokeLLM[Invoke LLM]
    
    InvokeLLM -->|Success| ReturnSuccess[Return enhanced_text<br/>+ explanation]
    
    InvokeLLM -->|OpenAIModerationError| ModerationError[Return empty text<br/>+ moderation message]
    
    InvokeLLM -->|APITimeoutError<br/>LangChainException| TimeoutError{Timeout<br/>mentioned?}
    TimeoutError -->|Yes| ReturnTimeout[Return original_text<br/>+ timeout message]
    TimeoutError -->|No| ReturnProcessingError[Return original_text<br/>+ processing error]
    
    InvokeLLM -->|RateLimitError| ReturnRateLimit[Return original_text<br/>+ rate limit message]
    
    InvokeLLM -->|APIError| CheckTokens{Token/Length<br/>error?}
    CheckTokens -->|Yes| ReturnTokenLimit[Return original_text<br/>+ token limit message]
    CheckTokens -->|No| ReturnAPIError[Return original_text<br/>+ API error message]
    
    InvokeLLM -->|Exception| ReturnGeneric[Return original_text<br/>+ generic error message]
    
    ReturnSuccess --> End
    ModerationError --> End
    ReturnTimeout --> End
    ReturnProcessingError --> End
    ReturnRateLimit --> End
    ReturnTokenLimit --> End
    ReturnAPIError --> End
    ReturnGeneric --> End
```

## 7. Estrutura de Dados do Estado (EnhancementGraphState)

```mermaid
classDiagram
    class EnhancementGraphState {
        +string field_name
        +string text
        +dict field_info
        +string enhanced_text
        +string explanation
        +list[FieldEnhancement] enhancement_history
        +string previous_fields_summary
        +string campaign_name
    }
    
    class FieldEnhancement {
        +string field_name
        +string original_text
        +string enhanced_text
        +string explanation
        +string timestamp
    }
    
    class EnhancedTextResponse {
        +string enhanced_text
        +string explanation
    }
    
    EnhancementGraphState "contains" --> FieldEnhancement : enhancement_history
    EnhancementGraphState --> EnhancedTextResponse : result
```

## Tabelas do Banco de Dados

### enhanceable_fields
Armazena configurações de campos que podem ser aprimorados.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `field_name` | VARCHAR(100) | PK - Nome técnico do campo |
| `display_name` | VARCHAR(200) | Nome de exibição |
| `expectations` | TEXT | O que se espera do campo |
| `improvement_guidelines` | TEXT | Diretrizes de melhoria |
| `created_at` | TIMESTAMP | Data de criação |
| `updated_at` | TIMESTAMP | Data de atualização |

**Campos pré-configurados:**
- `businessObjective` - Objetivo de Negócio
- `expectedResult` - Resultado Esperado / KPI Principal
- `targetAudienceDescription` - Descrição do Público-Alvo
- `exclusionCriteria` - Critérios de Exclusão

### audit_interactions
Registra todas as interações com IA para auditoria e análise.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | VARCHAR | PK - UUID |
| `user_id` | VARCHAR | ID do usuário (indexed) |
| `campaign_id` | VARCHAR | ID da campanha (indexed, nullable) |
| `field_name` | VARCHAR(100) | Nome do campo (indexed) |
| `input_text` | TEXT | Texto original |
| `output_text` | TEXT | Texto aprimorado |
| `explanation` | TEXT | Explicação do aprimoramento |
| `session_id` | VARCHAR | ID da sessão (indexed, nullable) |
| `user_decision` | VARCHAR(20) | Decisão: 'approved'/'rejected' (indexed, nullable) |
| `decision_at` | TIMESTAMP | Data da decisão (nullable) |
| `created_at` | TIMESTAMP | Data de criação (indexed) |

**Índices:**
- `ix_audit_interactions_user_id`
- `ix_audit_interactions_campaign_id`
- `ix_audit_interactions_field_name`
- `ix_audit_interactions_session_id`
- `ix_audit_interactions_user_campaign` (composite: user_id, campaign_id)
- `ix_audit_interactions_session` (session_id)
- `ix_audit_interactions_created_at`
- `ix_audit_interactions_user_decision`

### checkpoints (LangGraph)
Tabelas criadas automaticamente pelo LangGraph para checkpointing.

| Tabela | Descrição |
|--------|-----------|
| `checkpoints` | Armazena estados do grafo por thread_id |
| `checkpoint_blobs` | Armazena blobs grandes de estado |

**Estrutura checkpoints:**
- `thread_id` (PK) - Identificador da thread/sessão
- `checkpoint_ns` (PK) - Namespace
- `checkpoint_id` (PK) - ID do checkpoint
- `parent_checkpoint_id` - Checkpoint pai (para histórico)
- `checkpoint` - Estado serializado (JSON)
- `metadata` - Metadados adicionais (JSONB)

