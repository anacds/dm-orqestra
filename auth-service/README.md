# Auth Service

Microservice responsável por autenticação e gerenciamento de usuários.

## Funcionalidades

- Registro de usuários
- Login e autenticação JWT
- Refresh tokens
- Logout
- Auditoria de tentativas de login
- Rate limiting

## Endpoints

- `POST /api/auth/register` - Registrar novo usuário
- `POST /api/auth/login` - Login (retorna JWT)
- `POST /api/auth/refresh` - Renovar access token
- `POST /api/auth/logout` - Revogar refresh token
- `GET /api/auth/me` - Obter informações do usuário atual
- `GET /api/auth/users/{user_id}` - Obter informações de um usuário específico
- `GET /api/health` - Health check do serviço
- `GET /` - Informações básicas do serviço

## Porta

8002

## Banco de Dados

- Database: `auth_service`
- Tabelas: `users`, `refresh_tokens`, `login_audits`

