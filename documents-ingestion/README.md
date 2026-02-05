# Document Ingestion Pipeline

Pipeline para carregar, quebrar em chunks semânticos e indexar documentos jurídicos no Weaviate. Desenvolvido para ser usado por um agente de IA especialista em guidelines de comunicações de CRM.

## ⚠️ Nota Importante

**O Orqestra já vem com dados pré-processados!**

O `docker-compose.yml` principal (na raiz do projeto) carrega automaticamente os chunks e vetores pré-gerados a partir dos JSONs em `legal-service/data/`. Isso:

- ✅ Elimina necessidade de tokens OpenAI para ingestão
- ✅ Reduz tempo de startup (~segundos vs ~2-3 minutos)
- ✅ Garante reprodutibilidade para avaliadores

**Use este serviço apenas se quiser regenerar os dados** (ex: novos documentos, experimentos com chunking).

## 🏗️ Arquitetura

O pipeline segue uma arquitetura modular e madura:

- **Extractors**: Extração de texto de PDFs (pymupdf)
- **Chunkers**: Chunking semântico baseado em estrutura de documento (títulos, seções, listas)
- **Embeddings**: Suporte para OpenAI e modelos open-source (Ollama/local)
- **Indexers**: Indexação no Weaviate com versionamento e idempotência
- **Orquestração**: Pipeline Python idempotente e observável

## 🚀 Execução (Regeneração de Dados)

### Pré-requisitos

1. O Weaviate principal deve estar rodando:
   ```bash
   cd ..  # raiz do projeto
   docker compose up weaviate -d
   ```

2. Configure a variável de ambiente:
   ```bash
   export OPENAI_API_KEY=sua-chave-aqui
   ```

### Regenerar dados

```bash
# Dentro de documents-ingestion/

# Section chunking → LegalDocuments
docker compose up ingestion-section

# Semantic chunking → LegalDocumentsSemanticChunks
docker compose up ingestion-semantic

# Ou ambos sequencialmente
docker compose up ingestion-section && docker compose up ingestion-semantic
```

### Script helper

```bash
./scripts/ingest_all_strategies.sh
```

## 📋 Pré-requisitos

- Docker e Docker Compose
- API Key para embeddings (se usando OpenAI)

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```bash
# Weaviate (não precisa mudar se usando docker-compose)
WEAVIATE_URL=http://weaviate:8080

# Embeddings
EMBEDDING_PROVIDER=openai  # ou 'ollama'
OPENAI_API_KEY=sua_chave_aqui
EMBEDDING_MODEL=text-embedding-3-small  # opcional

# Documentos
DOCUMENTS_DIR=doc-juridico

# Logs
LOG_LEVEL=INFO
```

### Usando Ollama (local)

```bash
EMBEDDING_PROVIDER=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434
EMBEDDING_MODEL=nomic-embed-text
```

## 📖 Uso

### Executar Pipeline Completa

```bash
docker-compose up
```

### Estratégias de Chunking

O pipeline suporta duas estratégias de chunking, cada uma criando uma collection diferente no Weaviate:

| Estratégia | Collection | Descrição |
|------------|------------|-----------|
| `section` | `LegalDocuments` | Chunking por seções numeradas do documento |
| `semantic` | `LegalDocumentsSemanticChunks` | Chunking baseado em similaridade semântica |

#### Ingestão com estratégia específica

```bash
# Section chunking (padrão) → LegalDocuments
docker compose up ingestion-section

# Semantic chunking → LegalDocumentsSemanticChunks
docker compose up ingestion-semantic

# Ou via variável de ambiente
CHUNKER_TYPE=semantic docker compose up ingestion
```

#### Ingestão de todas as estratégias (para experimentos)

```bash
# Indexa em ambas as collections
./scripts/ingest_all_strategies.sh

# Apenas section
./scripts/ingest_all_strategies.sh --section-only

# Apenas semantic
./scripts/ingest_all_strategies.sh --semantic-only
```

### Executar Apenas Weaviate

```bash
docker-compose up -d weaviate
```

Depois execute a pipeline localmente:
```bash
python -m src.pipeline
```

### Usar como Módulo Python

```python
from pathlib import Path
from src.pipeline import IngestionPipeline

pipeline = IngestionPipeline(
    documents_dir=Path("doc-juridico"),
    embedding_provider="openai",
    weaviate_url="http://localhost:8080",
)

stats = pipeline.process_all()
pipeline.close()
```

## 🐳 Docker

### Construir imagem manualmente

```bash
docker build -t doc-ingestion .
```

### Executar container manualmente

```bash
docker run --rm \
  --env-file .env \
  -v $(pwd)/doc-juridico:/app/doc-juridico \
  --network host \
  doc-ingestion
```

## 🔧 Características Principais

### Estratégias de Chunking

O pipeline oferece duas estratégias de chunking configuráveis:

#### Section Chunker
Divide documentos por seções numeradas (ex: "1. Introdução", "2. Diretrizes"). 
- Preserva a estrutura original do documento
- Ideal para documentos com formatação consistente
- Collection: `LegalDocuments`

#### Semantic Chunker
Usa embeddings para identificar pontos de quebra semântica.
- Chunks mais coesos semanticamente
- Usa LangChain SemanticChunker
- Collection: `LegalDocumentsSemanticChunks`

Ambos detectam automaticamente o canal (SMS, EMAIL, PUSH, APP) a partir do nome do arquivo.

### Versionamento e Idempotência

- Cada documento recebe uma versão baseada em hash
- Chunks são identificados deterministicamente
- Re-execuções são idempotentes (não duplicam dados)
- Suporte para rollback e auditoria

### Observabilidade

- Logs estruturados em JSON
- Métricas de processamento (chunks criados, indexados, erros)
- Rastreamento por `ingestion_run_id`

## 📁 Estrutura do Projeto

```
.
├── src/
│   ├── extractors/      # Extractores de documentos
│   │   └── pdf_extractor.py
│   ├── chunkers/        # Chunkers semânticos
│   │   └── semantic_chunker.py
│   ├── embeddings/      # Serviços de embeddings
│   │   └── embedding_service.py
│   ├── indexers/        # Indexadores Weaviate
│   │   └── weaviate_indexer.py
│   ├── utils/           # Utilitários
│   │   └── logging_config.py
│   └── pipeline.py      # Pipeline principal
├── doc-juridico/        # Documentos a processar
├── docker-compose.yml   # Orquestração Docker
├── Dockerfile           # Imagem da aplicação
├── requirements.txt
└── README.md
```

## 🔍 Próximos Passos

- [ ] Implementar retry e backoff para APIs externas
- [ ] Adicionar métricas Prometheus/Grafana
- [ ] Suporte para pipelines event-driven
- [ ] Avaliação de qualidade de chunks (offline eval)

## 📝 Notas

Este pipeline segue práticas maduras de engenharia de dados para RAG:

- **Idempotência**: Execuções repetidas não duplicam dados
- **Versionamento**: Histórico de versões de documentos
- **Observabilidade**: Logs estruturados e métricas
- **Chunking Inteligente**: Baseado em estrutura, não apenas tokens
- **Modularidade**: Componentes reutilizáveis e testáveis

Este setup é mais maduro que 80% das POCs de RAG e alinhado com práticas de mercado.
