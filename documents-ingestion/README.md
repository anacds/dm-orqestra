# Document Ingestion Pipeline

Pipeline para extrair texto de PDFs, quebrar em chunks e indexar no Weaviate. Usado para alimentar o RAG do Legal Service.

O Orqestra já vem com dados pré-processados no `legal-service/data/`. Use este pipeline apenas se quiser regenerar os dados (novos documentos ou experimentos com chunking).

## Estratégias de chunking

| Estratégia | Collection | Descrição |
|---|---|---|
| `section` | `LegalDocuments` | Quebra por seções numeradas do documento |
| `semantic` | `LegalDocumentsSemanticChunks` | Quebra por similaridade semântica via embeddings |

## Execução

Requer Weaviate rodando e `OPENAI_API_KEY` configurada.

```bash
# Subir Weaviate (se não estiver rodando)
cd ..
docker compose up weaviate -d

# Voltar e rodar a ingestão
cd documents-ingestion
export OPENAI_API_KEY=sua-chave

# Section chunking
docker compose up ingestion-section

# Semantic chunking
docker compose up ingestion-semantic
```

Ou localmente:

```bash
pip install -r requirements.txt
python -m src.pipeline
```

## Variáveis de ambiente

| Variável | Default | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | -- | Chave da OpenAI (obrigatória) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Modelo de embeddings |
| `WEAVIATE_URL` | `http://localhost:8080` | URL do Weaviate |
| `DOCUMENTS_DIR` | `doc-juridico` | Diretório com PDFs |
| `CHUNKER_TYPE` | `section` | Estratégia de chunking |
| `CLEAR_BEFORE_INGEST` | `true` | Limpar collection antes de ingerir |
