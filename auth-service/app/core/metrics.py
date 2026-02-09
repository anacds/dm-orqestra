"""Prometheus custom metrics for the Auth Service."""

from prometheus_client import Counter

# --- Login ---
LOGIN_ATTEMPTS = Counter(
    "auth_login_attempts_total",
    "Total de tentativas de login",
    ["result", "failure_reason"],  # success/failure, invalid_credentials/inactive_user/none
)

# --- Token ---
TOKEN_REFRESHES = Counter(
    "auth_token_refreshes_total",
    "Total de renovações de token",
    ["result"],  # success / expired / invalid
)

# --- Registration ---
USER_REGISTRATIONS = Counter(
    "auth_user_registrations_total",
    "Total de registros de novos usuários",
    ["result"],  # success / duplicate
)

# --- Logout ---
LOGOUTS = Counter(
    "auth_logouts_total",
    "Total de logouts",
)
