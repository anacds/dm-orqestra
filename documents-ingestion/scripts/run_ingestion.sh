#!/bin/bash
# Script para executar a pipeline de ingestão

set -e

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run pipeline
python -m src.pipeline

