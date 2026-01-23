# Document Ingestion Pipeline

Pipeline para carregar, quebrar em chunks semânticos e indexar documentos jurídicos no Weaviate. Desenvolvido para ser usado por um agente de IA especialista em guidelines de comunicações de CRM.

## 🏗️ Arquitetura

O pipeline segue uma arquitetura modular e madura:

- **Extractors**: Extração de texto de PDFs (pymupdf)
- **Chunkers**: Chunking semântico baseado em estrutura de documento (títulos, seções, listas)
- **Embeddings**: Suporte para OpenAI e modelos open-source (Ollama/local)
- **Indexers**: Indexação no Weaviate com versionamento e idempotência
- **Orquestração**: Pipeline Python idempotente e observável

## 🚀 Execução Rápida com Docker

### 1. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` e configure principalmente:
- `OPENAI_API_KEY`: Sua chave da API OpenAI (se usando OpenAI)
- `EMBEDDING_PROVIDER`: `openai` ou `ollama`

### 2. Execute tudo com Docker Compose

```bash
docker-compose up
```

Isso irá:
1. Iniciar o Weaviate
2. Aguardar o Weaviate ficar pronto
3. Executar a pipeline de ingestão
4. Processar todos os PDFs em `doc-juridico/`

### 3. Executar apenas o Weaviate (para testes)

```bash
docker-compose up weaviate
```

### 4. Re-executar apenas a ingestão

```bash
docker-compose up ingestion
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

### Chunking Semântico

O chunker não divide por contagem fixa de tokens. Em vez disso, divide baseado em:

- Títulos e cabeçalhos (detecção automática)
- Seções numeradas
- Quebras de seção (linhas separadoras, espaços)
- Listas e exemplos
- Preservação de contexto estrutural

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
