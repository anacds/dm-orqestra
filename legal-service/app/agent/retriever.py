import logging
import os
from typing import List, Dict, Optional
import weaviate
from weaviate.classes.query import MetadataQuery, Filter, Rerank
from app.core.config import settings
from app.core.models_config import load_models_config

logger = logging.getLogger(__name__)


class HybridWeaviateRetriever:
    """Hybrid search retriever for Weaviate (sem reranking)."""

    def __init__(
        self,
        weaviate_url: Optional[str] = None,
        api_key: Optional[str] = None,
        class_name: str = None,
        embedding_model: Optional[str] = None,
    ):
        self.weaviate_url = weaviate_url or settings.WEAVIATE_URL
        self.api_key = api_key or settings.WEAVIATE_API_KEY
        self.class_name = class_name or settings.WEAVIATE_CLASS_NAME
        
        config = load_models_config()
        embeddings_config = config.get("models", {}).get("embeddings", {})
        self.embedding_model = embedding_model or embeddings_config.get("model", "text-embedding-3-small")
        
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Weaviate."""
        try:
            url_clean = self.weaviate_url.replace("https://", "").replace("http://", "")
            host_parts = url_clean.split("/")[0].split(":")
            http_host = host_parts[0]
            http_port = int(host_parts[1]) if len(host_parts) > 1 else 8080
            
            logger.info(f"Connecting to Weaviate: host={http_host}, port={http_port}, url={self.weaviate_url}")
            
            auth_config = weaviate.auth.AuthApiKey(api_key=self.api_key) if self.api_key else None
            self.client = weaviate.connect_to_custom(
                http_host=http_host,
                http_port=http_port,
                http_secure=False,
                grpc_host=http_host,
                grpc_port=50051,
                grpc_secure=False,
                auth_credentials=auth_config,
            )
            
            self.client.connect()

            logger.info(f"Successfully connected to Weaviate at {self.weaviate_url}")
        except Exception as e:
            logger.error(f"Error connecting to Weaviate: {e}")
            logger.error(f"Connection details: host={http_host if 'http_host' in locals() else 'unknown'}, port={http_port if 'http_port' in locals() else 'unknown'}, url={self.weaviate_url}")
            raise
    
    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text using OpenAI."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        alpha: float = 0.5,
        channel: Optional[str] = None,
        query_title: Optional[str] = None,
        query_body: Optional[str] = None,
    ) -> List[Dict]:
        """Perform hybrid search (vector + BM25) sem reranking.
        
        Args:
            query: Search query text (usado como fallback ou para SMS)
            limit: Maximum number of results to return
            alpha: Weight for vector search (0.0 = BM25 only, 1.0 = vector only)
            channel: Filter by communication channel
            query_title: Title text for PUSH notifications (optional)
            query_body: Body text for SMS or PUSH (optional)
        
        Returns:
            List of document chunks with metadata
        """
        try:
            collection = self.client.collections.get(self.class_name)
            
            where_filter = None
            if channel:
                where_filter = (
                    Filter.by_property("channel").equal(channel) |
                    Filter.by_property("channel").equal("GENERAL")
                )
                logger.info(f"Filtering by channel: {channel} or GENERAL")
            
            config = load_models_config()
            retrieval_config = config.get("models", {}).get("retrieval", {})
            retrieval_limit = max(limit, int(retrieval_config.get("limit", limit)))
            rerank_enabled = retrieval_config.get("rerank_enabled", False)
            rerank_property = retrieval_config.get("rerank_property", "text")
            
            # Se reranking está habilitado, define quantos chunks retornar após reranking
            # Se não especificado, usa o limit original
            if rerank_enabled:
                final_limit = retrieval_config.get("rerank_top_k", limit)
                logger.info(
                    f"[RETRIEVAL] Reranking config: buscar {retrieval_limit} chunks, "
                    f"retornar top {final_limit} após reranking"
                )
            else:
                final_limit = limit
            
            # Para PUSH com title/body, constrói query melhorada incluindo ambos
            # Os documentos indexados são guidelines (texto contínuo), então buscamos apenas em "text"
            if channel == "PUSH" and query_title and query_body:
                # Query melhorada: inclui title e body para melhor matching com guidelines
                enhanced_query = f"{query_title} {query_body}"
                logger.info(
                    f"[RETRIEVAL] PUSH com title/body - query melhorada. "
                    f"Retrieving {retrieval_limit} chunks"
                )
                query_embedding = self._get_embedding(enhanced_query)
                search_query = enhanced_query
            else:
                # Busca normal para SMS e outros canais
                logger.info(
                    f"[RETRIEVAL] Retrieving {retrieval_limit} chunks, selecting top {limit} by hybrid score"
                )
                query_embedding = self._get_embedding(query)
                search_query = query
            
            query_kwargs = {
                "query": search_query,
                "vector": query_embedding,
                "alpha": alpha,
                "limit": retrieval_limit,
                "return_metadata": MetadataQuery(
                    score=True,
                    explain_score=True
                ),
                "return_properties": ["text", "source_file", "file_name", 
                                     "chunk_index", "section_name", "section_number", 
                                     "page_number", "channel"]
            }
            
            # Adiciona reranking se habilitado
            if rerank_enabled:
                query_kwargs["rerank"] = Rerank(
                    prop=rerank_property,
                    query=search_query
                )
                logger.info(
                    f"[RETRIEVAL] Reranking enabled - property: {rerank_property}, "
                    f"query: {search_query[:100]}..."
                )
            
            if where_filter:
                query_kwargs["filters"] = where_filter
            
            try:
                response = collection.query.hybrid(**query_kwargs)
            except Exception as e:
                logger.error(f"[RETRIEVAL] Hybrid query failed: {e}")
                raise
            
            total_retrieved = len(response.objects) if response.objects else 0
            
            if rerank_enabled:
                logger.info(
                    f"[RETRIEVAL] Hybrid search returned {total_retrieved} objects, "
                    f"reranked to top {final_limit}"
                )
            else:
                logger.info(
                    f"[RETRIEVAL] Hybrid search returned {total_retrieved} objects, "
                    f"selecting top {limit} by hybrid score"
                )
            
            results = []
            channels_found = set()
            if response.objects:
                objects_to_process = response.objects[:final_limit]
                
                # Log detalhado dos chunks retornados
                if rerank_enabled:
                    logger.info(f"[RETRIEVAL] Chunks após reranking (top {final_limit} de {total_retrieved}):")
                else:
                    logger.info(f"[RETRIEVAL] Chunks selecionados (top {limit}):")
                
                for idx, obj in enumerate(objects_to_process, start=1):
                    props = obj.properties
                    channel = props.get("channel")
                    if channel:
                        channels_found.add(channel)
                    
                    score = None
                    hybrid_score = None
                    rerank_score = None
                    
                    if obj.metadata:
                        hybrid_score = getattr(obj.metadata, "score", None)
                        rerank_score = getattr(obj.metadata, "rerank_score", None)
                        # Prioriza rerank_score se disponível, senão usa hybrid_score
                        score = rerank_score if rerank_score is not None else hybrid_score
                    
                    file_name = props.get("file_name", props.get("source_file", "unknown"))
                    text_preview = props.get("text", "")[:80] + "..." if len(props.get("text", "")) > 80 else props.get("text", "")
                    
                    if rerank_enabled:
                        score_info = f"rerank={rerank_score:.4f}" if rerank_score is not None else "rerank=N/A"
                        if hybrid_score is not None:
                            score_info += f", hybrid={hybrid_score:.4f}"
                        logger.info(
                            f"  [{idx}] {file_name} | {score_info} | "
                            f"channel={channel or 'N/A'} | {text_preview}"
                        )
                    else:
                        score_info = f"hybrid={hybrid_score:.4f}" if hybrid_score is not None else "score=N/A"
                        logger.info(
                            f"  [{idx}] {file_name} | {score_info} | "
                            f"channel={channel or 'N/A'} | {text_preview}"
                        )
                    
                    result = {
                        "text": props.get("text", ""),
                        "source_file": props.get("source_file", ""),
                        "file_name": props.get("file_name", ""),
                        "chunk_index": props.get("chunk_index", 0),
                        "section_name": props.get("section_name"),
                        "section_number": props.get("section_number"),
                        "page_number": props.get("page_number"),
                        "channel": channel,
                        "score": score,
                    }
                    results.append(result)
            
            if channels_found:
                logger.info(f"[RETRIEVAL] Channels found in results: {sorted(channels_found)}")
            else:
                logger.warning("[RETRIEVAL] No channels found in results (all may be None)")
            
            rerank_status = "[RERANKED]" if rerank_enabled else "[NO RERANK]"
            logger.info(
                f"[RETRIEVAL] Final: {len(results)} results for query: '{query[:50]}...'"
                + (f" (channel: {channel})" if channel else "")
                + f" {rerank_status}"
            )
            return results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}", exc_info=True)
            return []
    
    def close(self):
        """Close Weaviate connection."""
        if hasattr(self, 'client') and self.client:
            self.client.close()

