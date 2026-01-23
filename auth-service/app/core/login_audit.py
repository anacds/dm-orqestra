from typing import Optional
from sqlalchemy.orm import Session
from uuid import uuid4
from app.models.login_audit import LoginAudit
from app.models.user import User


def log_login_attempt(
    db: Session,
    email: str,
    success: bool,
    user: Optional[User] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    failure_reason: Optional[str] = None
):
    audit = LoginAudit(
        id=str(uuid4()),
        user_id=user.id if user else None,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        failure_reason=failure_reason
    )
    db.add(audit)
    db.commit()

