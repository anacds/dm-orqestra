# campaigns-mcp-server

Serviço MCP (Model Context Protocol) que expõe a tool **`retrieve_piece_content`**, responsável por buscar o conteúdo de peças criativas (E-mail ou App) no **campaigns-service**.

## Tool

- **`retrieve_piece_content`**(`campaign_id`, `piece_id`, `commercial_space`?)
  - Chama `GET /api/campaigns/{campaign_id}/creative-pieces/{piece_id}/content` no campaigns-service.
  - **E-mail**: retorna `contentType: text/html` e `content` com o HTML (JSON-safe).
  - **App**: exige `commercial_space`; retorna `contentType: image/png` e `content` como data URL base64.

## Transport

- **Streamable HTTP** em `/mcp` (padrão do FastMCP).
- Porta configurável via `PORT` (default `8010`).

## Configuração

Ver `env.example`. Principais variáveis:

- `CAMPAIGNS_SERVICE_URL`: URL do campaigns-service.
- `PORT`: Porta do servidor MCP.
- `MCP_SERVICE_*`: headers usados ao chamar o campaigns (identity de serviço).

## Uso

### Docker Compose

O `docker-compose` do projeto sobe o `campaigns-mcp-server` e o conecta ao `campaigns-service`.

### Local

```bash
pip install -r requirements.txt
export CAMPAIGNS_SERVICE_URL=http://localhost:8003  # ou via gateway
python server.py
```

### Cliente MCP

Conectar ao endpoint Streamable HTTP:

```
http://localhost:8010/mcp
```

Ex.: MCP Inspector, Claude Code, ou outro cliente que suporte Streamable HTTP.

## Dependências

- **campaigns-service**: precisa estar rodando e com o endpoint de download disponível.
- O serviço chama o campaigns com headers `X-User-*` (usuário de serviço). O campaigns não valida existência do usuário; apenas exige os headers.
