from typing import Dict, Optional
from fastapi import HTTPException, status, Request
import base64


async def get_current_user(request: Request) -> Dict:
    def decode_header_value(value: str) -> str:
        if not value:
            return ""
        if value.startswith("base64:"):
            encoded = value[7:]
            try:
                return base64.b64decode(encoded).decode('utf-8')
            except Exception:
                return value
        return value
    
    user_id = decode_header_value(request.headers.get("X-User-Id", ""))
    user_email = decode_header_value(request.headers.get("X-User-Email", ""))
    user_role = decode_header_value(request.headers.get("X-User-Role", ""))
    is_active = request.headers.get("X-User-Is-Active", "false").lower() == "true"
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return {
        "id": user_id,
        "email": user_email or "",
        "role": user_role or "",
        "is_active": is_active
    }


async def get_token_from_cookie_or_header(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    
    return None

