"""Prometheus custom metrics for the Campaigns Service."""

from prometheus_client import Counter, Histogram

# --- CRUD Operations ---
CAMPAIGN_OPERATIONS = Counter(
    "campaigns_operations_total",
    "Total de operações CRUD em campanhas",
    ["operation"],  # create / update / delete / list / get
)

# --- Status Transitions ---
STATUS_TRANSITIONS = Counter(
    "campaigns_status_transitions_total",
    "Total de transições de status de campanhas",
    ["from_status", "to_status"],
)

# --- Piece Reviews ---
REVIEW_SUBMISSIONS = Counter(
    "campaigns_review_submissions_total",
    "Total de submissões de peças para revisão",
    ["channel"],
)

REVIEW_VERDICTS = Counter(
    "campaigns_review_verdicts_total",
    "Total de vereditos de revisão humana",
    ["channel", "verdict"],  # approved / rejected
)

# --- S3 Uploads ---
S3_UPLOADS = Counter(
    "campaigns_s3_uploads_total",
    "Total de uploads para S3",
    ["status"],  # success / error
)

S3_UPLOAD_DURATION = Histogram(
    "campaigns_s3_upload_duration_seconds",
    "Duração de uploads para S3",
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# --- MCP Tool ---
MCP_TOOL_CALLS = Counter(
    "campaigns_mcp_tool_calls_total",
    "Total de chamadas a ferramentas MCP",
    ["tool_name"],
)
