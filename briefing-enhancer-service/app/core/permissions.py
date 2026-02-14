from typing import Dict
from fastapi import HTTPException, status


BUSINESS_ANALYST_ROLE = "Analista de negócios"


def require_business_analyst(current_user: Dict) -> None:
    user_role = current_user.get("role")
    
    if user_role != BUSINESS_ANALYST_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta funcionalidade é restrita a analistas de negócios"
        )

