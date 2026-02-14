# Campaigns Service

Gerencia o ciclo de vida de campanhas, peças criativas, comentários e upload de arquivos para S3. Também expõe um MCP server com tools de acesso a peças e specs de canais.

Porta: 8003

## Endpoints REST

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/campaigns` | Listar campanhas |
| POST | `/api/campaigns` | Criar campanha |
| GET | `/api/campaigns/{id}` | Detalhe da campanha |
| PUT | `/api/campaigns/{id}` | Atualizar campanha |
| DELETE | `/api/campaigns/{id}` | Remover campanha |
| GET | `/api/campaigns/my-tasks` | Tarefas do usuário |
| POST | `/api/campaigns/{id}/comments` | Adicionar comentário |
| POST | `/api/campaigns/{id}/creative-pieces` | Submeter peça (SMS/Push) |
| POST | `/api/campaigns/{id}/creative-pieces/upload` | Upload de arquivo (Email/App) |
| GET | `/api/campaigns/{id}/creative-pieces/{pid}/content` | Conteúdo da peça |
| DELETE | `/api/campaigns/{id}/creative-pieces/{pid}` | Remover peça |

## MCP Tools (Streamable HTTP em `/mcp`)

| Tool | Descrição |
|---|---|
| `retrieve_piece_content` | Download do conteúdo de uma peça (HTML ou imagem base64) |
| `get_channel_specs` | Especificações técnicas por canal/espaço comercial |

## Execução manual

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8003
```

## Variáveis de ambiente

Ver `env.example`.
