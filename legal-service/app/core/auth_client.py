from typing import Dict
from fastapi import HTTPException, status, Request
import base64


async def get_current_user(request: Request) -> Dict:
    """
    Obtém o usuário atual dos cabeçalhos definidos pelo api gateway.
    o gateway valida a autenticação e passa o contexto do usuário via cabeçalhos.
    """
    def decode_header_value(value: str) -> str:
        """Decodifica o valor do cabeçalho codificado em base64, se necessário."""
        if not value:
            return ""
        if value.startswith("base64:"):
            encoded = value[7:]
            try:
                return base64.b64decode(encoded).decode('utf-8')
            except Exception:
                return value
        return value

    user_id = decode_header_value(request.headers.get("x-user-id", ""))
    user_email = decode_header_value(request.headers.get("x-user-email", ""))
    user_role = decode_header_value(request.headers.get("x-user-role", ""))
    is_active = request.headers.get("x-user-is-active", "false").lower() == "true"

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

