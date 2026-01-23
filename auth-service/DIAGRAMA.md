# Auth Service - Diagrama e Funcionalidades

## Funcionalidades

O Auth Service é responsável por toda a autenticação e gerenciamento de usuários do sistema Orqestra. Ele implementa autenticação baseada em JWT (JSON Web Tokens) com suporte a refresh tokens para renovação automática de sessões, garantindo que os usuários não precisem fazer login constantemente. O serviço gerencia o ciclo completo de autenticação, desde o registro de novos usuários até o logout e revogação de tokens. Durante o processo de login, todas as tentativas são auditadas em uma tabela dedicada, registrando informações como endereço IP, user-agent do navegador e resultado da tentativa (sucesso ou falha com motivo), proporcionando rastreabilidade completa para fins de segurança e monitoramento. O serviço também implementa rate limiting configurável para proteger contra ataques de força bruta, com limites específicos para login (50 requisições por minuto) e registro (5 requisições por hora), impedindo que atacantes tentem descobrir senhas através de tentativas massivas. Os tokens são armazenados em cookies HTTP-only com flag secure em produção, prevenindo acesso via JavaScript (proteção contra XSS) e garantindo transmissão apenas via HTTPS em ambientes de produção. O serviço suporta múltiplos roles de usuário através de um enum (Analista de negócios, Analista de criação, Analista de campanhas), permitindo controle de acesso baseado em permissões. Além disso, o serviço fornece endpoints para consulta de informações de usuários, permitindo que outros serviços do sistema obtenham dados de usuários específicos quando necessário, como no caso do campaigns-service que busca informações do criador de campanhas para exibição na interface. A senha dos usuários é armazenada usando hash bcrypt, garantindo que mesmo em caso de vazamento do banco de dados, as senhas não possam ser recuperadas em texto plano. O serviço também implementa validação de usuários ativos, impedindo que contas desativadas façam login no sistema.

## Endpoints

### POST /api/auth/register
Registra um novo usuário no sistema. Aceita email, senha, nome completo e role opcional. Valida se o email já está cadastrado e cria o usuário com senha hasheada usando bcrypt. Rate limit: 5 requisições por hora.

### POST /api/auth/login
Autentica um usuário com email e senha. Retorna access token JWT e refresh token, armazenando ambos em cookies HTTP-only. Registra tentativa de login na auditoria. Valida se o usuário está ativo. Rate limit: 50 requisições por minuto.

### POST /api/auth/refresh
Renova o access token usando um refresh token válido. Valida se o refresh token não está revogado e não expirou. Atualiza os cookies com o novo access token. Se o refresh token for renovado, atualiza também o cookie do refresh token.

### POST /api/auth/logout
Revoga o refresh token do usuário e remove os cookies de autenticação. Requer autenticação (usuário deve estar logado).

### GET /api/auth/me
Retorna informações do usuário autenticado (id, email, nome, role, status ativo). Usado principalmente pelo API Gateway para validar tokens e obter contexto do usuário. Requer autenticação.

### GET /api/auth/users/{user_id}
Retorna informações de um usuário específico pelo ID. Usado por outros serviços (como campaigns-service) para obter dados de usuários. Requer autenticação.

### GET /api/health
Endpoint de health check que retorna status do serviço.

### GET /
Endpoint raiz que retorna informações básicas do serviço (nome, versão, status).

## Diagrama de Arquitetura

```mermaid
graph TB
    Client[Cliente/Frontend] --> Gateway[API Gateway]
    Gateway --> AuthService[Auth Service<br/>Porta 8002]
    
    AuthService --> CORS[CORS Middleware]
    CORS --> RateLimit[Rate Limiting<br/>slowapi]
    RateLimit --> Routes[Router]
    
    Routes --> Register[POST /register]
    Routes --> Login[POST /login]
    Routes --> Refresh[POST /refresh]
    Routes --> Logout[POST /logout]
    Routes --> Me[GET /me]
    Routes --> GetUser[GET /users/:id]
    
    Register --> AuthServiceClass[AuthService]
    Login --> AuthServiceClass
    Refresh --> AuthServiceClass
    Logout --> AuthServiceClass
    Me --> AuthServiceClass
    GetUser --> AuthServiceClass
    
    AuthServiceClass --> Security[Security Module<br/>JWT, bcrypt]
    AuthServiceClass --> Database[(PostgreSQL<br/>auth_service)]
    AuthServiceClass --> Audit[Login Audit]
    
    Security --> JWT[JWT Tokens]
    Security --> Hash[Password Hashing<br/>bcrypt]
    
    Database --> Users[users table]
    Database --> RefreshTokens[refresh_tokens table]
    Database --> LoginAudits[login_audits table]
    
    Audit --> LoginAudits
    
    style AuthService fill:#4a90e2,stroke:#2c5aa0,color:#fff
    style Security fill:#e74c3c,stroke:#c0392b,color:#fff
    style Database fill:#27ae60,stroke:#229954,color:#fff
    style RateLimit fill:#9b59b6,stroke:#7d3c98,color:#fff
```

## Fluxo de Autenticação

```mermaid
sequenceDiagram
    participant C as Cliente
    participant G as API Gateway
    participant A as Auth Service
    participant DB as Database
    participant Audit as Login Audit
    
    C->>G: POST /api/auth/login
    G->>A: POST /api/auth/login
    A->>A: Verificar rate limit
    A->>DB: Buscar usuário por email
    DB-->>A: Dados do usuário
    
    alt Credenciais inválidas
        A->>Audit: Registrar tentativa falha
        A-->>G: 401 Unauthorized
        G-->>C: 401 Unauthorized
    else Usuário inativo
        A->>Audit: Registrar tentativa falha
        A-->>G: 403 Forbidden
        G-->>C: 403 Forbidden
    else Credenciais válidas
        A->>A: Gerar JWT access token
        A->>A: Gerar refresh token
        A->>DB: Salvar refresh token
        A->>Audit: Registrar tentativa sucesso
        A->>A: Definir cookies (access_token, refresh_token)
        A-->>G: TokenResponse + Set-Cookie
        G-->>C: TokenResponse + Cookies
    end
```

## Fluxo de Validação de Token (API Gateway)

```mermaid
sequenceDiagram
    participant C as Cliente
    participant G as API Gateway
    participant A as Auth Service
    participant DB as Database
    
    C->>G: Requisição com cookie access_token
    G->>G: Extrair token do cookie
    G->>G: Decodificar JWT (validar assinatura)
    
    alt Token inválido/expirado
        G-->>C: 401 Unauthorized
    else Token válido
        G->>A: GET /api/auth/me (com token)
        A->>A: Validar token
        A->>DB: Buscar usuário por email
        DB-->>A: Dados do usuário
        
        alt Usuário não encontrado/inativo
            A-->>G: 401/403
            G-->>C: 401/403
        else Usuário válido
            A-->>G: UserResponse
            G->>G: Adicionar headers X-User-*
            G->>Backend: Proxy com headers
            Backend-->>G: Response
            G-->>C: Response
        end
    end
```

## Modelo de Dados

```mermaid
erDiagram
    USERS ||--o{ REFRESH_TOKENS : "tem"
    USERS ||--o{ LOGIN_AUDITS : "gera"
    
    USERS {
        string id PK
        string email UK
        string hashed_password
        string full_name
        string role
        boolean is_active
        boolean is_superuser
    }
    
    REFRESH_TOKENS {
        string id PK
        string user_id FK
        string token UK
        datetime expires_at
        boolean is_revoked
        datetime created_at
    }
    
    LOGIN_AUDITS {
        string id PK
        string user_id FK
        string email
        string ip_address
        string user_agent
        boolean success
        string failure_reason
        datetime created_at
    }
```

## Componentes Internos

```mermaid
graph LR
    subgraph "Auth Service"
        Main[main.py<br/>FastAPI App]
        Routes[routes.py<br/>Endpoints]
        Services[services.py<br/>Business Logic]
        Security[security.py<br/>JWT, bcrypt]
        Config[config.py<br/>Settings]
        RateLimit[rate_limit.py<br/>Rate Limiting]
        Audit[login_audit.py<br/>Audit Logging]
    end
    
    subgraph "Models"
        User[user.py]
        RefreshToken[refresh_token.py]
        LoginAudit[login_audit.py]
    end
    
    subgraph "Schemas"
        AuthSchemas[auth.py<br/>Pydantic Models]
    end
    
    Main --> Routes
    Routes --> Services
    Services --> Security
    Services --> Audit
    Services --> User
    Services --> RefreshToken
    Services --> LoginAudit
    Routes --> AuthSchemas
    Main --> Config
    Main --> RateLimit
    
    style Main fill:#3498db
    style Services fill:#2ecc71
    style Security fill:#e74c3c
    style Config fill:#9b59b6
```

## Fluxo de Refresh Token

```mermaid
sequenceDiagram
    participant C as Cliente
    participant G as API Gateway
    participant A as Auth Service
    participant DB as Database
    
    C->>G: POST /api/auth/refresh<br/>(com refresh_token cookie)
    G->>A: POST /api/auth/refresh
    
    A->>DB: Buscar refresh token
    DB-->>A: Token encontrado
    
    alt Token não encontrado/revogado
        A-->>G: 401 Unauthorized
        G-->>C: 401 Unauthorized
    else Token expirado
        A-->>G: 401 Unauthorized
        G-->>C: 401 Unauthorized
    else Token válido
        A->>DB: Buscar usuário
        DB-->>A: Dados do usuário
        
        alt Usuário inativo
            A-->>G: 401 Unauthorized
            G-->>C: 401 Unauthorized
        else Usuário ativo
            A->>A: Gerar novo access token
            A->>A: Definir cookie access_token
            A-->>G: TokenResponse
            G-->>C: TokenResponse + Cookie
        end
    end
```

## Segurança

```mermaid
graph TB
    subgraph "Camadas de Segurança"
        RateLimit[Rate Limiting<br/>Proteção contra força bruta]
        PasswordHash[Password Hashing<br/>bcrypt]
        JWT[JWT Tokens<br/>Assinados com SECRET_KEY]
        HttpOnly[HTTP-Only Cookies<br/>Proteção XSS]
        Secure[Secure Cookies<br/>Apenas em produção]
        Audit[Login Audit<br/>Rastreamento de tentativas]
    end
    
    RateLimit --> Login[Login Endpoint]
    RateLimit --> Register[Register Endpoint]
    
    PasswordHash --> Register
    PasswordHash --> Login
    
    JWT --> Login
    JWT --> Refresh
    JWT --> Me
    
    HttpOnly --> Login
    HttpOnly --> Refresh
    
    Secure --> Login
    Secure --> Refresh
    
    Audit --> Login
    
    style RateLimit fill:#e74c3c
    style PasswordHash fill:#3498db
    style JWT fill:#f39c12
    style HttpOnly fill:#27ae60
    style Secure fill:#9b59b6
    style Audit fill:#34495e,color:#fff
```

