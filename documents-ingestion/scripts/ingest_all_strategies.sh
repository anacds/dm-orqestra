#!/bin/bash
# =============================================================================
# INGEST ALL STRATEGIES
# =============================================================================
# Este script indexa os documentos em múltiplas collections com diferentes
# estratégias de chunking para permitir experimentos de avaliação.
#
# Uso:
#   ./scripts/ingest_all_strategies.sh
#   ./scripts/ingest_all_strategies.sh --section-only
#   ./scripts/ingest_all_strategies.sh --semantic-only
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=============================================================="
echo "DOCUMENTS INGESTION - Multiple Strategies"
echo "=============================================================="
echo ""

# Parse argumentos
SECTION_ONLY=false
SEMANTIC_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --section-only)
            SECTION_ONLY=true
            shift
            ;;
        --semantic-only)
            SEMANTIC_ONLY=true
            shift
            ;;
        *)
            echo "Uso: $0 [--section-only|--semantic-only]"
            exit 1
            ;;
    esac
done

# Verifica se Weaviate está rodando
echo "[1/3] Verificando Weaviate..."
if ! docker compose ps weaviate | grep -q "running"; then
    echo "    Weaviate não está rodando. Iniciando..."
    docker compose up -d weaviate
    echo "    Aguardando Weaviate ficar healthy..."
    sleep 10
fi
echo "    ✓ Weaviate está rodando"
echo ""

# Ingestão por seção
if [ "$SEMANTIC_ONLY" = false ]; then
    echo "[2/3] Ingestão com SECTION chunking..."
    echo "    Collection: LegalDocuments"
    docker compose run --rm ingestion-section
    echo "    ✓ Ingestão section concluída"
    echo ""
fi

# Ingestão semântica
if [ "$SECTION_ONLY" = false ]; then
    echo "[3/3] Ingestão com SEMANTIC chunking..."
    echo "    Collection: LegalDocumentsSemanticChunks"
    docker compose run --rm ingestion-semantic
    echo "    ✓ Ingestão semantic concluída"
    echo ""
fi

echo "=============================================================="
echo "INGESTÃO CONCLUÍDA"
echo "=============================================================="
echo ""
echo "Collections disponíveis no Weaviate:"

if [ "$SEMANTIC_ONLY" = false ]; then
    echo "  - LegalDocuments (section chunking)"
fi
if [ "$SECTION_ONLY" = false ]; then
    echo "  - LegalDocumentsSemanticChunks (semantic chunking)"
fi

echo ""
echo "Para testar experimentos no legal-service:"
echo "  docker compose exec legal-service python evals/run_experiments.py --list"
echo ""
