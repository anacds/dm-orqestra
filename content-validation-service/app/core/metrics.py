"""Prometheus custom metrics for the Content Validation Service."""

from prometheus_client import Counter, Histogram

# --- Pipeline ---
VALIDATION_TOTAL = Counter(
    "cv_validation_total",
    "Total de validações executadas",
    ["channel", "verdict"],  # SMS/PUSH/EMAIL/APP, APROVADO/REPROVADO
)

VALIDATION_DURATION = Histogram(
    "cv_validation_duration_seconds",
    "Duração total do pipeline de validação por canal",
    ["channel"],
    buckets=(1, 5, 10, 30, 60, 120, 180, 300),
)

# --- Nodes ---
NODE_DURATION = Histogram(
    "cv_node_duration_seconds",
    "Duração de execução de cada nó do grafo",
    ["node", "channel"],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

# --- MCP Tool Calls ---
MCP_CALLS = Counter(
    "cv_mcp_calls_total",
    "Total de chamadas MCP a serviços externos",
    ["tool", "status"],  # tool name, success/error
)

MCP_DURATION = Histogram(
    "cv_mcp_duration_seconds",
    "Latência de chamadas MCP por ferramenta",
    ["tool"],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60),
)

# --- A2A (legal-service) ---
A2A_CALLS = Counter(
    "cv_a2a_calls_total",
    "Total de chamadas A2A ao legal-service",
    ["channel", "status"],  # success/error/timeout
)

A2A_DURATION = Histogram(
    "cv_a2a_duration_seconds",
    "Latência de chamadas A2A ao legal-service",
    ["channel"],
    buckets=(1, 5, 10, 30, 60, 120, 180, 300),
)

# --- Specs ---
SPECS_RESULT = Counter(
    "cv_specs_result_total",
    "Resultado das validações de specs",
    ["channel", "result"],  # pass / fail
)

# --- Branding ---
BRANDING_RESULT = Counter(
    "cv_branding_result_total",
    "Resultado das validações de branding",
    ["channel", "compliant"],  # true / false
)
