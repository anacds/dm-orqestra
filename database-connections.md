# Conexões aos bancos de dados do Orqestra

Todos os bancos rodam no mesmo container PostgreSQL (`db`), acessível em `localhost:5432`.

## Credenciais

| Parâmetro | Valor |
|---|---|
| Host | `localhost` |
| Porta | `5432` |
| Usuário | `orqestra` |
| Senha | `orqestra_password` |

## Bancos de dados

| Banco | Serviço |
|---|---|
| `auth_service` | Auth Service |
| `campaigns_service` | Campaigns Service |
| `briefing_enhancer` | Briefing Enhancer Service |
| `content_validation` | Content Validation Service |
| `legal_service` | Legal Service |
| `metabase` | Metabase (observabilidade) |

## Conexão via terminal

```bash
# Acessar o container
docker compose exec db psql -U orqestra

# Listar bancos
\l

# Conectar a um banco especifico
\c auth_service
\c campaigns_service
\c briefing_enhancer
\c content_validation
\c legal_service
```

## Connection strings (psql direto)

```bash
psql postgresql://orqestra:orqestra_password@localhost:5432/auth_service
psql postgresql://orqestra:orqestra_password@localhost:5432/campaigns_service
psql postgresql://orqestra:orqestra_password@localhost:5432/briefing_enhancer
psql postgresql://orqestra:orqestra_password@localhost:5432/content_validation
psql postgresql://orqestra:orqestra_password@localhost:5432/legal_service
```
