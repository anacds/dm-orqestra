from typing import Dict
from fastapi import HTTPException, status


CREATIVE_ANALYST_ROLE = "Analista de criação"
MARKETING_MANAGER_ROLE = "Gestor de marketing"

# Papéis autorizados a usar validação de IA
_AI_ALLOWED_ROLES = {CREATIVE_ANALYST_ROLE, MARKETING_MANAGER_ROLE}


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


def require_ai_validation_access(current_user: Dict) -> None:
    """
    Valida que o usuário pode executar validação de IA.
    Permite: Analista de criação e Gestor de marketing.
    """
    user_role = current_user.get("role", "")

    if user_role not in _AI_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta funcionalidade é restrita a analistas de criação e gestores de marketing"
        )
