"""Prometheus metrics for the Legal Service.

Metrics are organized by subsystem:
- llm_*     : LLM inference (latency, tokens, errors)
- rag_*     : RAG retrieval (Weaviate search, embedding, reranking)
- cache_*   : Redis cache (hits, misses, errors)
- agent_*   : End-to-end agent invocation
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# ---------------------------------------------------------------------------
# Agent (end-to-end)
# ---------------------------------------------------------------------------

AGENT_INVOCATIONS = Counter(
    "legal_agent_invocations_total",
    "Total agent invocations",
    ["channel", "decision"],  # channel=SMS|PUSH|EMAIL|APP, decision=APROVADO|REPROVADO
)

AGENT_DURATION = Histogram(
    "legal_agent_duration_seconds",
    "End-to-end agent invocation duration",
    ["channel"],
    buckets=(1, 2, 5, 10, 20, 30, 60, 90, 120, 180, 300),
)

AGENT_ERRORS = Counter(
    "legal_agent_errors_total",
    "Agent invocation errors",
    ["channel", "error_type"],  # error_type=timeout|token_limit|validation|unknown
)

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

LLM_REQUEST_DURATION = Histogram(
    "legal_llm_request_duration_seconds",
    "LLM inference duration",
    ["provider", "model", "channel"],
    buckets=(1, 2, 5, 10, 15, 20, 30, 45, 60, 90),
)

LLM_TOKENS = Counter(
    "legal_llm_tokens_total",
    "LLM tokens consumed",
    ["provider", "model", "type"],  # type=input|output
)

LLM_ERRORS = Counter(
    "legal_llm_errors_total",
    "LLM request errors",
    ["provider", "model", "error_type"],  # error_type=timeout|rate_limit|token_limit|other
)

# ---------------------------------------------------------------------------
# RAG Retrieval (Weaviate)
# ---------------------------------------------------------------------------

RAG_RETRIEVAL_DURATION = Histogram(
    "legal_rag_retrieval_duration_seconds",
    "Weaviate hybrid search duration (excluding embedding)",
    ["channel", "rerank_enabled"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 3, 5, 10),
)

RAG_EMBEDDING_DURATION = Histogram(
    "legal_rag_embedding_duration_seconds",
    "OpenAI embedding generation duration",
    ["model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

RAG_DOCUMENTS_RETRIEVED = Histogram(
    "legal_rag_documents_retrieved",
    "Number of documents retrieved per query",
    ["channel"],
    buckets=(0, 1, 2, 3, 5, 7, 10, 15, 20),
)

RAG_RERANK_DURATION = Histogram(
    "legal_rag_rerank_duration_seconds",
    "Cohere reranker duration (included in retrieval, measured separately)",
    ["channel"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 3, 5),
)

# ---------------------------------------------------------------------------
# Cache (Redis)
# ---------------------------------------------------------------------------

CACHE_OPERATIONS = Counter(
    "legal_cache_operations_total",
    "Cache operations",
    ["operation", "result"],  # operation=get|set, result=hit|miss|error
)

# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------

SERVICE_INFO = Info(
    "legal_service",
    "Legal service build information",
)
