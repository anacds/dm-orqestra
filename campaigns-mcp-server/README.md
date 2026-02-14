# Campaigns MCP Server (standalone)

Proxy MCP que expõe a tool `retrieve_piece_content` chamando a API REST do Campaigns Service. Usado quando o MCP client não tem acesso direto ao banco/S3.

Porta: 8010

## MCP Tool 

| Tool | Descrição |
|---|---|
| `retrieve_piece_content` | Download de peça criativa via API do campaigns-service |

## Execução manual

```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8010
```

## Variáveis de ambiente

Ver `env.example`.
