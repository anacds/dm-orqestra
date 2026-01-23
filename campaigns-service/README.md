# Campaigns Service - Documentação

## Funcionalidades 

O Campaigns Service é responsável pelo gerenciamento completo do ciclo de vida das campanhas de CRM, abrangendo sua criação, atualização, exclusão e acompanhamento ao longo de diferentes fases e status. O serviço implementa um modelo de controle de acesso baseado em papéis, no qual cada tipo de usuário possui permissões e níveis de visibilidade específicos, definidos de acordo com o status atual da campanha. As campanhas são gerenciadas por meio de um workflow baseado em status, no qual cada transição é validada conforme regras de negócio e o papel do usuário que executa a ação. 
O serviço também permite que campanhas tenham comentários associados, viabilizando a comunicação entre diferentes papéis ao longo do processo de revisão e aprovação. Além disso, gerencia as peças criativas, que podem assumir quatro formatos distintos: SMS (texto simples), Push (título e corpo), App (arquivos PNG associados a espaços comerciais específicos) e E-mail (arquivos HTML). Os arquivos são armazenados em um bucket S3 (utilizando LocalStack no ambiente local) com visualização em tela.
São aplicadas validações específicas conforme o tipo de canal. Para campanhas de App, os arquivos devem estar no formato PNG e estar associados a espaços comerciais previamente definidos na campanha. Para campanhas de E-mail, apenas arquivos HTML válidos são aceitos, com validações adicionais para impedir o upload de formatos inadequados, como RTF. Sempre que um arquivo é substituído, a versão anterior é automaticamente removida do S3, garantindo consistência e evitando acúmulo de arquivos obsoletos. No caso das peças de App, múltiplos arquivos podem ser vinculados a uma única peça criativa, sendo organizados em uma estrutura JSON que mapeia cada espaço comercial à respectiva URL do arquivo.

## Lista de Endpoints

### Campanhas

1. **GET /api/campaigns**
   - Lista campanhas visíveis ao usuário baseado no seu role
   - Query params: `skip` (padrão: 0), `limit` (padrão: 100)
   - Response: `CampaignsResponse`
   - Autenticação: Requerida

2. **GET /api/campaigns/{campaign_id}**
   - Obtém uma campanha específica por ID
   - Response: `CampaignResponse`
   - Autenticação: Requerida

3. **POST /api/campaigns**
   - Cria uma nova campanha
   - Body: `CampaignCreate`
   - Response: `CampaignResponse` (201)
   - Autenticação: Requerida
   - Permissão: Apenas Analista de Negócios

4. **PUT /api/campaigns/{campaign_id}**
   - Atualiza uma campanha existente
   - Body: `CampaignUpdate`
   - Response: `CampaignResponse`
   - Autenticação: Requerida
   - Valida: Transições de status baseadas em role

5. **DELETE /api/campaigns/{campaign_id}**
   - Deleta uma campanha
   - Response: 204 No Content
   - Autenticação: Requerida
   - Permissão: Apenas Analista de Negócios, apenas próprios rascunhos (DRAFT)

### Comentários

6. **POST /api/campaigns/{campaign_id}/comments**
   - Adiciona um comentário a uma campanha
   - Body: `CommentCreate`
   - Response: `CommentResponse` (201)
   - Autenticação: Requerida

### Creative Pieces

7. **POST /api/campaigns/{campaign_id}/creative-pieces**
   - Submete uma peça criativa (SMS ou Push)
   - Body: `CreativePieceCreate`
   - Response: `CreativePieceResponse` (201)
   - Autenticação: Requerida
   - Permissão: Apenas Analista de Criação
   - Restrição: Campanha deve estar em CREATIVE_STAGE ou CONTENT_ADJUSTMENT

8. **POST /api/campaigns/{campaign_id}/creative-pieces/upload-app**
   - Faz upload de arquivo PNG para canal App
   - Form data: `commercial_space` (string), `file` (PNG)
   - Response: `CreativePieceResponse` (201)
   - Autenticação: Requerida
   - Permissão: Apenas Analista de Criação
   - Restrição: Campanha deve estar em CREATIVE_STAGE ou CONTENT_ADJUSTMENT

9. **POST /api/campaigns/{campaign_id}/creative-pieces/upload-email**
   - Faz upload de arquivo HTML para canal E-mail
   - Form data: `file` (HTML)
   - Response: `CreativePieceResponse` (201)
   - Autenticação: Requerida
   - Permissão: Apenas Analista de Criação
   - Restrição: Campanha deve estar em CREATIVE_STAGE ou CONTENT_ADJUSTMENT

10. **DELETE /api/campaigns/{campaign_id}/creative-pieces/app/{commercial_space}**
    - Deleta um arquivo App específico de um espaço comercial
    - Response: 204 No Content
    - Autenticação: Requerida
    - Permissão: Apenas Analista de Criação
    - Restrição: Campanha deve estar em CREATIVE_STAGE ou CONTENT_ADJUSTMENT

11. **DELETE /api/campaigns/{campaign_id}/creative-pieces/email**
    - Deleta o arquivo HTML do canal E-mail
    - Response: 204 No Content
    - Autenticação: Requerida
    - Permissão: Apenas Analista de Criação
    - Restrição: Campanha deve estar em CREATIVE_STAGE ou CONTENT_ADJUSTMENT

### Health Check

12. **GET /api/health**
    - Health check do serviço
    - Response: `{"status": "ok", "service": "campaigns-service"}`

## Diagramas Mermaid

### Arquitetura do Serviço

```mermaid
graph TB
    Frontend[Frontend React] -->|HTTP| Gateway[API Gateway]
    Gateway -->|HTTP + Headers X-User-*| CampaignsService[Campaigns Service]
    CampaignsService -->|PostgreSQL| DB[(Database)]
    CampaignsService -->|S3 API| S3[LocalStack S3]
    CampaignsService -->|HTTP| AuthService[Auth Service]
    
    subgraph CampaignsService
        Routes[Routes Layer]
        Services[Services Layer]
        Models[Models Layer]
        Permissions[Permissions]
        S3Client[S3 Client]
        AuthClient[Auth Client]
        
        Routes --> Services
        Services --> Models
        Services --> Permissions
        Services --> S3Client
        Services --> AuthClient
    end
```

### Fluxo de Requisição

```mermaid
sequenceDiagram
    participant F as Frontend
    participant G as API Gateway
    participant CS as Campaigns Service
    participant DB as Database
    participant S3 as S3/LocalStack
    participant AS as Auth Service
    
    F->>G: GET /api/campaigns
    G->>G: Validate JWT Token
    G->>AS: GET /api/auth/me
    AS-->>G: User Info
    G->>CS: GET /api/campaigns<br/>+ X-User-* headers
    CS->>CS: Extract User Context
    CS->>DB: Query Campaigns (filtered by role)
    DB-->>CS: Campaigns Data
    CS->>AS: GET /api/auth/users/{id} (for creator names)
    AS-->>CS: User Details
    CS->>CS: Build Response
    CS-->>G: CampaignsResponse
    G-->>F: CampaignsResponse
```

### Modelo de Dados

```mermaid
erDiagram
    Campaign ||--o{ Comment : has
    Campaign ||--o{ CreativePiece : has
    
    Campaign {
        string id PK
        string name
        enum category
        string business_objective
        string expected_result
        enum requesting_area
        date start_date
        date end_date
        enum priority
        array communication_channels
        array commercial_spaces
        string target_audience_description
        string exclusion_criteria
        decimal estimated_impact_volume
        enum communication_tone
        enum execution_model
        enum trigger_event
        int recency_rule_days
        enum status
        string created_by
        datetime created_date
    }
    
    Comment {
        string id PK
        string campaign_id FK
        string author
        string role
        text text
        datetime timestamp
    }
    
    CreativePiece {
        string id PK
        string campaign_id FK
        string piece_type
        text text
        string title
        text body
        text file_urls
        string html_file_url
        datetime created_at
        datetime updated_at
    }
```

### Workflow de Status

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Business Analyst<br/>Creates Campaign
    DRAFT --> CREATIVE_STAGE: Business Analyst<br/>Submits
    CREATIVE_STAGE --> CONTENT_REVIEW: Creative Analyst<br/>Submits Content
    CONTENT_REVIEW --> CAMPAIGN_BUILDING: Business Analyst<br/>Approves
    CONTENT_REVIEW --> CONTENT_ADJUSTMENT: Business Analyst<br/>Rejects
    CONTENT_ADJUSTMENT --> CONTENT_REVIEW: Creative Analyst<br/>Resubmits
    CAMPAIGN_BUILDING --> CAMPAIGN_PUBLISHED: Campaign Analyst<br/>Publishes
    CAMPAIGN_PUBLISHED --> [*]
    DRAFT --> [*]: Business Analyst<br/>Deletes Own Draft
```

### Permissões por Role

```mermaid
graph LR
    BA[Business Analyst] -->|Can View| Status1[DRAFT]
    BA -->|Can View| Status2[CREATIVE_STAGE]
    BA -->|Can View| Status3[CONTENT_REVIEW]
    BA -->|Can View| Status4[CONTENT_ADJUSTMENT]
    BA -->|Can View| Status5[CAMPAIGN_BUILDING]
    BA -->|Can View| Status6[CAMPAIGN_PUBLISHED]
    
    CA[Creative Analyst] -->|Can View| Status2
    CA -->|Can View| Status3
    CA -->|Can View| Status4
    
    CmpA[Campaign Analyst] -->|Can View| Status5
    CmpA -->|Can View| Status6
```

### Componentes Internos

```mermaid
graph TD
    Main[main.py] --> Routes[routes.py]
    Main --> Config[config.py]
    Main --> S3Init[s3_client.py]
    
    Routes --> Dependencies[dependencies.py]
    Routes --> Services[services.py]
    Routes --> Permissions[permissions.py]
    Routes --> FileUpload[file_upload.py]
    Routes --> S3Client[s3_client.py]
    
    Services --> Models[models/]
    Services --> AuthClient[auth_client.py]
    Services --> Permissions
    
    FileUpload --> S3Client
    
    Models --> Campaign[campaign.py]
    Models --> Comment[comment.py]
    Models --> CreativePiece[creative_piece.py]
    Models --> UserRole[user_role.py]
    
    Dependencies -->|Reads| Headers[X-User-* Headers]
    AuthClient -->|Calls| AuthService[Auth Service API]
    S3Client -->|Uses| LocalStack[LocalStack S3]
```

