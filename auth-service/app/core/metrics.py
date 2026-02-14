from prometheus_client import Counter

LOGIN_ATTEMPTS = Counter(
    "auth_login_attempts_total",
    "Total de tentativas de login",
    ["result", "failure_reason"], 
)

TOKEN_REFRESHES = Counter(
    "auth_token_refreshes_total",
    "Total de renovações de token",
    ["result"],  # success / expired / invalid
)

USER_REGISTRATIONS = Counter(
    "auth_user_registrations_total",
    "Total de registros de novos usuários",
    ["result"],  
)

LOGOUTS = Counter(
    "auth_logouts_total",
    "Total de logouts",
)
