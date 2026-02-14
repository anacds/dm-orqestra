from prometheus_client import Counter, Histogram

ENHANCEMENT_TOTAL = Counter(
    "be_enhancement_total",
    "Total de requisições de aprimoramento de texto",
    ["field_name", "provider", "status"],  # success / moderation / timeout / rate_limit / error
)

ENHANCEMENT_DURATION = Histogram(
    "be_enhancement_duration_seconds",
    "Duração total do pipeline de aprimoramento",
    ["field_name", "provider"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
)

LLM_INVOCATIONS = Counter(
    "be_llm_invocations_total",
    "Total de invocações LLM para aprimoramento",
    ["provider", "model"],
)

MODERATION_REJECTIONS = Counter(
    "be_moderation_rejections_total",
    "Total de rejeições por moderação de conteúdo",
    ["field_name"],
)
