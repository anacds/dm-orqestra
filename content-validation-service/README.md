# Content Validation Service

Orchestrator for content validation using **LangGraph**. Same structure as legal-service and briefing-enhancer-service.

- **First step:** Validate format and size of the piece (SMS, PUSH, EMAIL, APP) via `validate` node.
- **Second step:** Orchestrate calls (e.g. legal-service); currently a placeholder.
- Exposes HTTP API for api-gateway routing.

## Setup

```bash
cp env.example .env
# Set LEGAL_SERVICE_URL as needed
```

## Run

```bash
uvicorn main:app --reload --port 8004
```

## Endpoints

- `GET /` — service info
- `GET /api/content-validation/health` — health check
- `POST /api/ai/analyze-piece` — validate format/size + orchestrate (body: `{ "task", "channel", "content" }`)
- `POST /api/ai/generate-text` — 501 Not Implemented

**A2A** (Agent-to-Agent): `GET /a2a/.well-known/agent-card.json`, `POST /a2a/v1/message:send`. Ver `app/a2a/README.md`.

## LangGraph Studio

To visualize and debug the graph in [LangGraph Studio](https://langchain-ai.github.io/langgraph/concepts/langgraph_studio/):

**Opção rápida** (cria venv, instala deps e sobe o Studio):

```bash
./run_studio.sh
```

**Manual:** Python 3.11+ required.

1. Create venv and install CLI:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt 'langgraph-cli[inmem]>=0.2.6'
   ```
2. From this directory, create `.env` from `env.example`. For local Studio, use `localhost` URLs (e.g. `LEGAL_SERVICE_URL=http://localhost:8005`, `CAMPAIGNS_MCP_URL=http://localhost:8010`) if legal-service and campaigns-mcp-server run locally.
3. Run (use `--tunnel` to avoid "TypeError: Failed to fetch" no Chrome 142+, Safari ou Brave):
   ```bash
   .venv/bin/langgraph dev --tunnel
   ```
   O CLI exibe uma URL com `baseUrl=...trycloudflare.com` — use-a no browser. Alternativa no **Chrome**: smith.langchain.com -> cadeado -> "Local network access" -> **Allow**.
4. The Studio UI opens in the browser. Use the `content_validation` graph. Input shape:
   ```json
   {
     "task": "VALIDATE_COMMUNICATION",
     "channel": "SMS",
     "content": { "body": "Olá, teste." }
   }
   ```
   For EMAIL/APP use `"channel": "EMAIL"` or `"APP"` and `content` with `campaign_id`, `piece_id`, and `commercial_space` (APP only).

## Docker

Built as `content-validation-service`, port 8004. See `docker-compose.yml`.
