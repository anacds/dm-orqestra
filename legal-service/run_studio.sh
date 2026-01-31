#!/usr/bin/env bash
# Cria venv, instala deps + langgraph-cli[inmem] e sobe LangGraph Studio (langgraph dev).
set -e
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  echo "venv criado em .venv"
fi

.venv/bin/pip install -q -r requirements.txt 'langgraph-cli[inmem]>=0.2.6'
echo "Dependências instaladas."

if [[ ! -f .env ]]; then
  echo "Aviso: .env não encontrado. Copiando de env.example — ajuste WEAVIATE_URL, OPENAI_API_KEY, MARITACA_API_KEY conforme necessário."
  cp env.example .env
fi

# --tunnel evita "TypeError: Failed to fetch" (Chrome 142+ PNA, Safari, Brave).
# O CLI exibe uma URL com baseUrl=...trycloudflare.com — use-a no browser.
# Alternativa no Chrome: smith.langchain.com -> cadeado -> "Local network access" -> Allow.
echo "Subindo LangGraph Studio (langgraph dev --tunnel)..."
exec .venv/bin/langgraph dev --tunnel
