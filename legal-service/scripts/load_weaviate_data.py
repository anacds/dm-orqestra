#!/usr/bin/env python3
"""
Script para carregar dados pré-processados no Weaviate.

Carrega os JSONs exportados com chunks e vetores já prontos,
eliminando a necessidade de gerar embeddings durante a inicialização.

Uso:
    python scripts/load_weaviate_data.py

Variáveis de ambiente:
    WEAVIATE_URL: URL do Weaviate (default: http://localhost:8080)
    DATA_DIR: Diretório com os JSONs (default: data)
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.data import DataObject

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Mapeamento de arquivos JSON para collections
COLLECTIONS = {
    "LegalDocuments.json": "LegalDocuments",
    "LegalDocumentsSemanticChunks.json": "LegalDocumentsSemanticChunks",
}

# Schema das collections (deve corresponder ao weaviate_indexer.py)
COLLECTION_PROPERTIES = [
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
]


def wait_for_weaviate(url: str, max_retries: int = 30, delay: int = 2) -> bool:
    """Aguarda Weaviate ficar disponível."""
    logger.info(f"Aguardando Weaviate em {url}...")
    
    for attempt in range(max_retries):
        try:
            client = weaviate.connect_to_local(
                host=url.replace("http://", "").replace("https://", "").split(":")[0],
                port=int(url.split(":")[-1]) if ":" in url.split("/")[-1] else 8080,
            )
            if client.is_ready():
                client.close()
                logger.info("Weaviate está pronto!")
                return True
            client.close()
        except Exception as e:
            logger.debug(f"Tentativa {attempt + 1}/{max_retries}: {e}")
        
        time.sleep(delay)
    
    return False


def create_collection(client: weaviate.WeaviateClient, name: str) -> bool:
    """Cria uma collection se não existir."""
    try:
        if client.collections.exists(name):
            # Verifica se já tem dados
            collection = client.collections.get(name)
            count = collection.aggregate.over_all(total_count=True).total_count
            if count > 0:
                logger.info(f"Collection {name} já existe com {count} objetos. Pulando.")
                return False
            else:
                logger.info(f"Collection {name} existe mas está vazia. Carregando dados...")
                return True
        
        logger.info(f"Criando collection {name}...")
        client.collections.create(
            name=name,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=COLLECTION_PROPERTIES,
            reranker_config=Configure.Reranker.cohere(),
        )
        logger.info(f"Collection {name} criada com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao criar collection {name}: {e}")
        raise


def load_json_to_collection(
    client: weaviate.WeaviateClient,
    json_path: Path,
    collection_name: str,
    batch_size: int = 100,
) -> int:
    """Carrega dados de um JSON para uma collection."""
    logger.info(f"Carregando {json_path} para {collection_name}...")
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if not data:
        logger.warning(f"Arquivo {json_path} está vazio!")
        return 0
    
    collection = client.collections.get(collection_name)
    total = len(data)
    loaded = 0
    errors = 0
    
    logger.info(f"Total de objetos a carregar: {total}")
    
    # Processa em batches
    for i in range(0, total, batch_size):
        batch = data[i:i + batch_size]
        objects_to_insert = []
        
        for obj in batch:
            try:
                # Extrai dados do formato exportado
                additional = obj.get("_additional", {})
                obj_uuid = additional.get("id")
                vector = additional.get("vector", [])
                
                # Propriedades (tudo exceto _additional)
                properties = {k: v for k, v in obj.items() if k != "_additional"}
                
                # Cria objeto para inserção
                data_object = DataObject(
                    properties=properties,
                    vector=vector,
                    uuid=UUID(obj_uuid) if obj_uuid else None,
                )
                objects_to_insert.append(data_object)
                
            except Exception as e:
                logger.error(f"Erro ao processar objeto: {e}")
                errors += 1
        
        # Insere batch
        if objects_to_insert:
            try:
                result = collection.data.insert_many(objects_to_insert)
                
                # Conta erros no resultado
                if hasattr(result, 'errors') and result.errors:
                    for error in result.errors.values():
                        logger.error(f"Erro ao inserir: {error}")
                        errors += 1
                
                loaded += len(objects_to_insert) - (len(result.errors) if hasattr(result, 'errors') and result.errors else 0)
                
            except Exception as e:
                logger.error(f"Erro ao inserir batch: {e}")
                errors += len(objects_to_insert)
        
        # Log de progresso
        progress = min(i + batch_size, total)
        logger.info(f"Progresso: {progress}/{total} ({progress * 100 // total}%)")
    
    logger.info(f"Carregamento concluído: {loaded} objetos, {errors} erros")
    return loaded


def main():
    """Função principal."""
    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    
    logger.info("=" * 60)
    logger.info("Iniciando carga de dados no Weaviate")
    logger.info("=" * 60)
    logger.info(f"Weaviate URL: {weaviate_url}")
    logger.info(f"Data dir: {data_dir}")
    
    # Aguarda Weaviate
    if not wait_for_weaviate(weaviate_url):
        logger.error("Weaviate não está disponível!")
        sys.exit(1)
    
    # Conecta ao Weaviate
    try:
        host = weaviate_url.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(weaviate_url.split(":")[-1]) if ":" in weaviate_url.split("/")[-1] else 8080
        
        client = weaviate.connect_to_local(host=host, port=port)
        logger.info("Conectado ao Weaviate!")
    except Exception as e:
        logger.error(f"Erro ao conectar ao Weaviate: {e}")
        sys.exit(1)
    
    try:
        total_loaded = 0
        
        for json_file, collection_name in COLLECTIONS.items():
            json_path = data_dir / json_file
            
            if not json_path.exists():
                logger.warning(f"Arquivo não encontrado: {json_path}")
                continue
            
            # Cria collection se necessário
            should_load = create_collection(client, collection_name)
            
            if should_load:
                loaded = load_json_to_collection(client, json_path, collection_name)
                total_loaded += loaded
        
        logger.info("=" * 60)
        logger.info(f"Carga finalizada! Total: {total_loaded} objetos")
        logger.info("=" * 60)
        
    finally:
        client.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
