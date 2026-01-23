from typing import Optional, Dict
from fastapi import Request, HTTPException, status
from jose import JWTError, jwt
from app.config import SECRET_KEY, ALGORITHM, AUTH_SERVICE_URL
import httpx
import logging

logger = logging.getLogger(__name__)


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from cookie or Authorization header."""
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    return None


def decode_jwt_token(token: str) -> Optional[Dict]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidSignatureError:
        logger.error("JWT signature validation failed - SECRET_KEY mismatch")
        return None
    except JWTError:
        return None


async def get_user_from_auth_service(token: str) -> Optional[Dict]:
    """Fetch user information from auth-service."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.TimeoutException:
            logger.error("Timeout calling auth-service")
            return None
        except httpx.ConnectError:
            logger.error("Could not connect to auth-service")
            return None
        except Exception as e:
            logger.error(f"Error calling auth-service: {type(e).__name__}: {e}")
            return None


async def validate_and_extract_user(request: Request) -> Optional[Dict]:
    """Validate JWT and extract user context from auth-service."""
    token = get_token_from_request(request)
    if not token:
        return None
    
    payload = decode_jwt_token(token)
    if not payload:
        return None
    
    email = payload.get("sub")
    if not email:
        return None
    
    user = await get_user_from_auth_service(token)
    if not user:
        return None
    
    if not user.get("is_active", False):
        return None
    
    return user


def should_skip_auth(path: str) -> bool:
    """Check if authentication should be skipped for this path."""
    skip_paths = [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/api/health",
    ]
    if path == "/":
        return True
    return any(path.startswith(skip) for skip in skip_paths)

