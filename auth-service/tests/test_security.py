from unittest.mock import patch
from datetime import timedelta


# ── Hashing de senha ──────────────────────────────────────────────────────

def test_hash_and_verify_password():
    from app.core.security import get_password_hash, verify_password
    hashed = get_password_hash("minha_senha_123")
    assert hashed != "minha_senha_123"
    assert verify_password("minha_senha_123", hashed)


def test_verify_wrong_password():
    from app.core.security import get_password_hash, verify_password
    hashed = get_password_hash("senha_correta")
    assert not verify_password("senha_errada", hashed)


def test_hash_generates_different_salts():
    from app.core.security import get_password_hash
    h1 = get_password_hash("mesma_senha")
    h2 = get_password_hash("mesma_senha")
    assert h1 != h2  # bcrypt gera salt diferente a cada chamada


# ── JWT ───────────────────────────────────────────────────────────────────

AUTH_CONFIG = {"auth": {"algorithm": "HS256", "access_token_expire_minutes": 30}}


@patch("app.core.security.load_auth_config", return_value=AUTH_CONFIG)
@patch("app.core.security.settings")
def test_create_and_decode_access_token(mock_settings, mock_config):
    mock_settings.SECRET_KEY = "test-secret-key"
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"sub": "user@test.com"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user@test.com"
    assert payload["type"] == "access"


@patch("app.core.security.load_auth_config", return_value=AUTH_CONFIG)
@patch("app.core.security.settings")
def test_create_token_with_custom_expiry(mock_settings, mock_config):
    mock_settings.SECRET_KEY = "test-secret-key"
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"sub": "a@b.com"}, expires_delta=timedelta(hours=2))
    payload = decode_access_token(token)
    assert payload is not None


@patch("app.core.security.load_auth_config", return_value=AUTH_CONFIG)
@patch("app.core.security.settings")
def test_decode_expired_token(mock_settings, mock_config):
    mock_settings.SECRET_KEY = "test-secret-key"
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"sub": "x@y.com"}, expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


@patch("app.core.security.load_auth_config", return_value=AUTH_CONFIG)
@patch("app.core.security.settings")
def test_decode_invalid_token(mock_settings, mock_config):
    mock_settings.SECRET_KEY = "test-secret-key"
    from app.core.security import decode_access_token
    assert decode_access_token("token.invalido.aqui") is None


def test_create_refresh_token():
    from app.core.security import create_refresh_token
    token = create_refresh_token()
    assert isinstance(token, str)
    assert len(token) > 20  # token_urlsafe(32) gera ~43 chars


# ── Rate limiting ─────────────────────────────────────────────────────────

RATE_ENABLED = {"auth": {"rate_limit": {"enabled": True, "login_per_minute": 10, "register_per_hour": 50}}}
RATE_DISABLED = {"auth": {"rate_limit": {"enabled": False}}}


@patch("app.core.rate_limit.load_auth_config", return_value=RATE_ENABLED)
def test_login_rate_limit_enabled(mock_config):
    from app.core.rate_limit import get_login_rate_limit
    assert get_login_rate_limit() == "10/minute"


@patch("app.core.rate_limit.load_auth_config", return_value=RATE_DISABLED)
def test_login_rate_limit_disabled(mock_config):
    from app.core.rate_limit import get_login_rate_limit
    assert get_login_rate_limit() == "1000/minute"


@patch("app.core.rate_limit.load_auth_config", return_value=RATE_ENABLED)
def test_register_rate_limit_enabled(mock_config):
    from app.core.rate_limit import get_register_rate_limit
    assert get_register_rate_limit() == "50/hour"


@patch("app.core.rate_limit.load_auth_config", return_value=RATE_DISABLED)
def test_register_rate_limit_disabled(mock_config):
    from app.core.rate_limit import get_register_rate_limit
    assert get_register_rate_limit() == "1000/hour"
