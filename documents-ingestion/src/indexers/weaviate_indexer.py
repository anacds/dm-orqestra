import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.data import DataObject

logger = logging.getLogger(__name__)


class WeaviateIndexer:
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        class_name: str = "DocumentChunk",
        vectorizer: Optional[str] = None,
    ):
        self.url = url or os.getenv("WEAVIATE_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("WEAVIATE_API_KEY")
        self.class_name = class_name
        self.vectorizer = vectorizer

        auth_config = weaviate.auth.AuthApiKey(api_key=self.api_key) if self.api_key else None

        url_clean = self.url.replace("https://", "").replace("http://", "")
        host_parts = url_clean.split("/")[0].split(":")
        http_host = host_parts[0]
        http_port = int(host_parts[1]) if len(host_parts) > 1 else (8080 if "localhost" in http_host or "127.0.0.1" in http_host else (443 if "https" in self.url else 80))
        
        if http_host in ["localhost", "127.0.0.1"]:
            self.client = weaviate.connect_to_local(
                host=http_host,
                port=http_port,
                grpc_port=50051,
            )
        else:
            self.client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure="https" in self.url,
                grpc_host=http_host,
                grpc_port=50051,
                grpc_secure="https" in self.url,
                auth_credentials=auth_config,
            )

        self._ensure_collection_exists()

    def delete_all_objects(self):
        """Deleta todos os objetos da collection (mantém o schema)."""
        try:
            if not self.client.collections.exists(self.class_name):
                logger.info(f"Collection {self.class_name} does not exist, nothing to delete")
                return 0
            
            collection = self.client.collections.get(self.class_name)
            
            # Deleta a collection inteira e recria (mais eficiente que deletar objeto por objeto)
            self.client.collections.delete(self.class_name)
            logger.info(f"Deleted collection {self.class_name}")
            
            # Recria a collection com o mesmo schema
            self._create_collection()
            logger.info(f"Recreated collection {self.class_name}")
            
            return 1
        except Exception as e:
            logger.error(f"Error deleting all objects: {e}")
            raise

    def _create_collection(self):
        """Cria a collection com o schema definido."""
        create_kwargs = {
            "name": self.class_name,
            # IMPORTANTE: Vetores são fornecidos externamente (OpenAI embeddings)
            "vectorizer_config": Configure.Vectorizer.none(),
            "properties": [
                Property(name="text", data_type=DataType.TEXT),
                Property(name="source_file", data_type=DataType.TEXT),
                Property(name="file_name", data_type=DataType.TEXT),
                Property(name="chunk_index", data_type=DataType.INT),
                Property(name="document_version", data_type=DataType.TEXT),
                Property(name="ingestion_run_id", data_type=DataType.TEXT),
                Property(name="ingestion_timestamp", data_type=DataType.DATE),
                Property(name="metadata", data_type=DataType.TEXT),
                Property(name="channel", data_type=DataType.TEXT),
                Property(name="section_name", data_type=DataType.TEXT),
                Property(name="section_number", data_type=DataType.INT),
                Property(name="page_number", data_type=DataType.INT),
            ],
            "reranker_config": Configure.Reranker.cohere(),
        }
        self.client.collections.create(**create_kwargs)

    def _ensure_collection_exists(self):
        try:
            collection_exists = self.client.collections.exists(self.class_name)

            if collection_exists:
                logger.info(f"Collection {self.class_name} already exists")
                return

            self._create_collection()
            logger.info(f"Created collection {self.class_name}")

        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise

    def _generate_chunk_id(
        self,
        source_file: str,
        chunk_index: int,
        document_version: str,
    ) -> str:
        content = f"{source_file}:{chunk_index}:{document_version}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _compute_document_version(self, file_path: Path, file_content_hash: str) -> str:
        timestamp = datetime.utcnow().isoformat()
        return f"{file_content_hash[:16]}:{timestamp}"

    def _compute_content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def index_chunks(
        self,
        chunks: List[dict],
        embeddings: List[List[float]],
        source_file: str,
        file_name: str,
        document_metadata: dict,
        ingestion_run_id: Optional[str] = None,
        document_version: Optional[str] = None,
    ) -> dict:
        if not chunks or not embeddings:
            logger.warning("No chunks or embeddings provided")
            return {"indexed": 0, "skipped": 0, "errors": 0}

        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        ingestion_run_id = ingestion_run_id or str(uuid.uuid4())
        ingestion_timestamp = datetime.utcnow().isoformat() + "Z"

        if document_version is None:
            content_hash = self._compute_content_hash(chunks[0]["text"])
            document_version = self._compute_document_version(
                Path(source_file), content_hash
            )

        collection = self.client.collections.get(self.class_name)

        indexed = 0
        skipped = 0
        errors = 0

        objects_to_insert = []

        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                chunk_id = self._generate_chunk_id(
                    source_file, idx, document_version
                )

                try:
                    existing = collection.query.fetch_object_by_id(chunk_id)
                    if existing is not None:
                        logger.debug(f"Chunk {idx} already exists, skipping")
                        skipped += 1
                        continue
                except Exception:
                    pass

                obj = {
                    "text": chunk["text"],
                    "source_file": source_file,
                    "file_name": file_name,
                    "chunk_index": idx,
                    "document_version": document_version,
                    "ingestion_run_id": ingestion_run_id,
                    "ingestion_timestamp": ingestion_timestamp,
                    "metadata": json.dumps(document_metadata, ensure_ascii=False),
                    "channel": chunk.get("channel"),
                    "section_name": chunk.get("section_name"),
                    "section_number": chunk.get("section_number"),
                    "page_number": chunk.get("page_number"),
                }

                try:
                    chunk_uuid = uuid.UUID(chunk_id)
                except ValueError:
                    chunk_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id)

                data_object = DataObject(
                    properties=obj,
                    vector=embedding,
                    uuid=chunk_uuid,
                )
                objects_to_insert.append(data_object)

            except Exception as e:
                logger.error(f"Error preparing chunk {idx} for indexing: {e}")
                errors += 1

        if objects_to_insert:
            try:
                collection.data.insert_many(objects_to_insert)
                indexed = len(objects_to_insert)
                logger.info(
                    f"Indexed {indexed} chunks for {file_name} "
                    f"(version: {document_version[:16]}...)"
                )
            except Exception as e:
                logger.error(f"Error batch inserting chunks: {e}")
                errors += len(objects_to_insert)
                indexed = 0

        return {
            "indexed": indexed,
            "skipped": skipped,
            "errors": errors,
            "document_version": document_version,
            "ingestion_run_id": ingestion_run_id,
        }

    def close(self):
        if self.client:
            self.client.close()


def create_weaviate_indexer(
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    class_name: Optional[str] = None,
    vectorizer: Optional[str] = None,
    **kwargs
) -> WeaviateIndexer:
    """Cria um WeaviateIndexer com as configurações fornecidas.
    
    Args:
        url: URL do Weaviate
        api_key: API key (opcional)
        class_name: Nome da collection no Weaviate (default: LegalDocuments)
        vectorizer: Vectorizer a usar (None = vetores externos)
    """
    # Usa class_name do env se não fornecido
    if class_name is None:
        class_name = os.getenv("WEAVIATE_CLASS_NAME", "LegalDocuments")
    
    return WeaviateIndexer(
        url=url,
        api_key=api_key,
        class_name=class_name,
        vectorizer=vectorizer,
    )

