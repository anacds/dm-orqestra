# Auth Service

Autenticação e gerenciamento de usuários. Emite e valida tokens JWT (access + refresh).

Porta: 8002

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/auth/register` | Registrar usuário |
| POST | `/api/auth/login` | Login (retorna access + refresh token) |
| POST | `/api/auth/refresh` | Renovar access token |
| GET | `/api/auth/me` | Dados do usuário autenticado |
| GET | `/api/auth/users/{id}` | Buscar usuário por ID |
| POST | `/api/auth/logout` | Logout (invalida refresh token) |

## Execução manual

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8002
```

## Variáveis de ambiente

Ver `env.example`.
