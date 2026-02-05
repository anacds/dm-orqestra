from typing import Dict
from fastapi import HTTPException, status


CREATIVE_ANALYST_ROLE = "Analista de criação"


def require_creative_analyst(current_user: Dict) -> None:
    """
    Valida que o usuário atual possui o papel 'Analista de criação'.
    Levanta HTTPException 403 se o usuário não tiver o papel requerido.
    """
    user_role = current_user.get("role", "")

    if user_role != CREATIVE_ANALYST_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta funcionalidade é restrita a analistas de criação"
        )
