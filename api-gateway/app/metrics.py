"""Prometheus custom metrics for the API Gateway."""

from prometheus_client import Counter, Histogram

# --- Proxy ---
PROXY_REQUESTS = Counter(
    "gateway_proxy_requests_total",
    "Total de requisições proxy enviadas para serviços downstream",
    ["target_service", "method", "status_code"],
)

PROXY_DURATION = Histogram(
    "gateway_proxy_duration_seconds",
    "Latência das requisições proxy por serviço downstream",
    ["target_service", "method"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

# --- Auth ---
AUTH_VALIDATIONS = Counter(
    "gateway_auth_validations_total",
    "Total de validações JWT no gateway",
    ["result"],  # success | failure | skipped
)

# --- Erros upstream ---
UPSTREAM_ERRORS = Counter(
    "gateway_upstream_errors_total",
    "Erros de comunicação com serviços downstream",
    ["target_service", "error_type"],  # timeout | connection | other
)
