from datetime import timedelta, datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.core.auth_config import load_auth_config
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.login_audit import log_login_attempt
from app.core.metrics import LOGIN_ATTEMPTS, TOKEN_REFRESHES, USER_REGISTRATIONS, LOGOUTS
from app.models.user import User, UserRole
from app.models.refresh_token import RefreshToken
from app.schemas.auth import UserCreate, UserResponse, RefreshTokenRequest, TokenResponse


class AuthService:

    @staticmethod
    def register_user(db: Session, user_data: UserCreate) -> UserResponse:
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            USER_REGISTRATIONS.labels(result="duplicate").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        role_value = user_data.role.value if user_data.role else UserRole.BUSINESS_ANALYST.value
        user = User(
            id=str(uuid4()),
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=role_value,
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        USER_REGISTRATIONS.labels(result="success").inc()
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        )
    
    @staticmethod
    def login_user(
        db: Session,
        email: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None
    ) -> TokenResponse:
        user = db.query(User).filter(User.email == email).first()
        
        if not user or not verify_password(password, user.hashed_password):
            LOGIN_ATTEMPTS.labels(result="failure", failure_reason="invalid_credentials").inc()
            log_login_attempt(
                db=db,
                email=email,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="invalid_credentials"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            LOGIN_ATTEMPTS.labels(result="failure", failure_reason="inactive_user").inc()
            log_login_attempt(
                db=db,
                email=email,
                success=False,
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="inactive_user"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        config = load_auth_config()
        auth_config = config.get("auth", {})
        access_token_expires = timedelta(minutes=auth_config.get("access_token_expire_minutes", 30))
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        
        refresh_token_value = create_refresh_token()
        refresh_token_expires = datetime.now(timezone.utc) + timedelta(days=auth_config.get("refresh_token_expire_days", 7))
        
        refresh_token = RefreshToken(
            id=str(uuid4()),
            user_id=user.id,
            token=refresh_token_value,
            expires_at=refresh_token_expires,
            is_revoked=False
        )
        db.add(refresh_token)
        db.commit()
        
        log_login_attempt(
            db=db,
            email=email,
            success=True,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        LOGIN_ATTEMPTS.labels(result="success", failure_reason="none").inc()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_value,
            token_type="bearer"
        )
    
    @staticmethod
    def refresh_access_token(db: Session, token_data: RefreshTokenRequest) -> TokenResponse:
        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token == token_data.refresh_token,
            RefreshToken.is_revoked == False
        ).first()
        
        if not refresh_token:
            TOKEN_REFRESHES.labels(result="invalid").inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        if refresh_token.expires_at < datetime.now(timezone.utc):
            TOKEN_REFRESHES.labels(result="expired").inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired"
            )
        
        user = db.query(User).filter(User.id == refresh_token.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        config = load_auth_config()
        auth_config = config.get("auth", {})
        access_token_expires = timedelta(minutes=auth_config.get("access_token_expire_minutes", 30))
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        
        TOKEN_REFRESHES.labels(result="success").inc()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token.token,
            token_type="bearer"
        )
    
    @staticmethod
    def logout_user(db: Session, refresh_token: str, user_id: str) -> dict:
        LOGOUTS.inc()
        token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token,
            RefreshToken.user_id == user_id
        ).first()
        
        if token:
            token.is_revoked = True
            db.commit()
        
        return {"message": "Logged out successfully"}
    
    @staticmethod
    def get_current_user_info(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        )

