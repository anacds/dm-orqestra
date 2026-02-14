import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import yaml
load_dotenv()
from src.chunkers.semantic_chunker import SemanticChunker
from src.chunkers.section_chunker import SectionChunker
from src.embeddings.embedding_service import create_embedding_service
from src.extractors.pdf_extractor import PDFExtractor
from src.indexers.weaviate_indexer import create_weaviate_indexer
from src.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "ingestion.yaml"


def load_ingestion_config() -> Dict[str, Any]:
    """Carrega configuração de ingestão do YAML."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def get_collection_name(chunker_type: str, config: Optional[Dict] = None) -> str:
    """Retorna o nome da collection baseado no tipo de chunker."""
    if config is None:
        config = load_ingestion_config()
    
    strategies = config.get("strategies", {})
    strategy_config = strategies.get(chunker_type, {})
    
    default_collections = {
        "section": "LegalDocuments",
        "semantic": "LegalDocumentsSemanticChunks",
    }
    
    return strategy_config.get("collection_name", default_collections.get(chunker_type, "LegalDocuments"))


class IngestionPipeline:
    def __init__(
        self,
        documents_dir: Path,
        embedding_model: Optional[str] = None,
        weaviate_url: Optional[str] = None,
        chunk_min_size: int = 100,
        chunk_max_size: int = 800,
        chunker_type: str = "semantic",
        clear_before_ingest: bool = False,
        collection_name: Optional[str] = None,
    ):
        self.documents_dir = Path(documents_dir)
        self.ingestion_run_id = str(uuid.uuid4())
        self.chunker_type = chunker_type
        self.clear_before_ingest = clear_before_ingest        
        self.config = load_ingestion_config()
        self.collection_name = collection_name or get_collection_name(chunker_type, self.config)

        if chunker_type == "section":
            self.chunker = SectionChunker(min_chunk_size=chunk_min_size)
        else:
            self.chunker = SemanticChunker(
                min_chunk_size=chunk_min_size,
                max_chunk_size=chunk_max_size,
                embedding_model=embedding_model,
            )
        self.embedding_service = create_embedding_service(model=embedding_model)
        
        # Passa collection_name para o indexer
        self.indexer = create_weaviate_indexer(
            url=weaviate_url,
            class_name=self.collection_name,
        )

        # Limpa todos os dados antes de ingerir (evita duplicação)
        if self.clear_before_ingest:
            logger.info(f"Clearing all existing data from {self.collection_name} before ingestion...")
            self.indexer.delete_all_objects()

        logger.info(
            f"Pipeline initialized: run_id={self.ingestion_run_id}, "
            f"chunker={chunker_type}, collection={self.collection_name}"
        )

    def process_document(self, file_path: Path) -> dict:
        logger.info(f"Processing document: {file_path.name}")

        stats = {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "status": "failed",
            "chunks_created": 0,
            "chunks_indexed": 0,
            "errors": [],
        }

        try:
            extractor = PDFExtractor()
            extracted = extractor.extract(file_path)
            text = extracted["text"]
            metadata = extracted.get("metadata", {})

            if not text or not text.strip():
                raise ValueError("No text was extracted from the document")

            chunks = self.chunker.chunk(text, file_name=file_path.name)
            
            stats["chunks_created"] = len(chunks)

            if not chunks:
                raise ValueError("No chunks were created from the document")

            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = self.embedding_service.embed_batch(chunk_texts)

            if len(embeddings) != len(chunks):
                raise ValueError(
                    f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings"
                )

            indexing_result = self.indexer.index_chunks(
                chunks=chunks,
                embeddings=embeddings,
                source_file=str(file_path),
                file_name=file_path.name,
                document_metadata=metadata,
                ingestion_run_id=self.ingestion_run_id,
            )

            stats["chunks_indexed"] = indexing_result["indexed"]
            stats["chunks_skipped"] = indexing_result.get("skipped", 0)
            stats["document_version"] = indexing_result.get("document_version")
            stats["status"] = "success"

            logger.info(
                f"Successfully processed {file_path.name}: "
                f"{stats['chunks_indexed']} chunks indexed"
            )

        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)
            stats["errors"].append(str(e))
            stats["status"] = "failed"

        return stats

    def process_all(self, file_pattern: str = "*") -> dict:
        logger.info(f"Starting batch processing from {self.documents_dir}")

        files = list(self.documents_dir.glob(f"{file_pattern}.pdf"))

        if not files:
            logger.warning(f"No supported files found in {self.documents_dir}")
            return {
                "total_files": 0,
                "processed": 0,
                "failed": 0,
                "total_chunks_indexed": 0,
            }

        logger.info(f"Found {len(files)} files to process")

        results = []
        for file_path in files:
            result = self.process_document(file_path)
            results.append(result)

        stats = {
            "ingestion_run_id": self.ingestion_run_id,
            "total_files": len(files),
            "processed": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "total_chunks_indexed": sum(r["chunks_indexed"] for r in results),
            "files": results,
        }

        logger.info(
            f"Batch processing complete: {stats['processed']}/{stats['total_files']} "
            f"files processed, {stats['total_chunks_indexed']} chunks indexed"
        )

        return stats

    def close(self):
        if self.indexer:
            self.indexer.close()
        logger.info("Pipeline closed")


def main():

    log_level = os.getenv("LOG_LEVEL", "INFO")
    structured = os.getenv("LOG_STRUCTURED", "false").lower() == "true"
    
    setup_logging(level=log_level, structured=structured)

    documents_dir = Path(os.getenv("DOCUMENTS_DIR", "doc-juridico"))
    embedding_model = os.getenv("EMBEDDING_MODEL")
    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    chunker_type = os.getenv("CHUNKER_TYPE", "section")
    clear_before_ingest = os.getenv("CLEAR_BEFORE_INGEST", "true").lower() == "true"

    # Collection name pode ser sobrescrito via env var
    collection_name = os.getenv("WEAVIATE_CLASS_NAME")
    
    # Determina collection baseado no chunker_type se não especificado
    if not collection_name:
        collection_name = get_collection_name(chunker_type)
    
    logger.info("="*60)
    logger.info("INGESTION PIPELINE CONFIGURATION")
    logger.info("="*60)
    logger.info(f"  Chunker Type: {chunker_type}")
    logger.info(f"  Collection: {collection_name}")
    logger.info(f"  Clear Before Ingest: {clear_before_ingest}")
    logger.info(f"  Documents Dir: {documents_dir}")
    logger.info("="*60)

    pipeline = IngestionPipeline(
        documents_dir=documents_dir,
        embedding_model=embedding_model,
        weaviate_url=weaviate_url,
        chunker_type=chunker_type,
        clear_before_ingest=clear_before_ingest,
        collection_name=collection_name,
    )

    try:
        stats = pipeline.process_all()
        logger.info(f"Pipeline completed: {stats}")
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()

