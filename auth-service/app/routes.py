from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional
from app.core.database import get_db
from app.core.rate_limit import limiter, get_login_rate_limit, get_register_rate_limit
from app.core.auth_config import load_auth_config
from app.models.user import User
from app.schemas.auth import UserCreate, UserResponse, RefreshTokenRequest, TokenResponse
from app.core.security import get_current_user
from app.core.config import settings
from app.services import AuthService

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_register_rate_limit())
async def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    return AuthService.register_user(db, user_data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_login_rate_limit())
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    email = form_data.username
    
    token_response = AuthService.login_user(
        db=db,
        email=email,
        password=form_data.password,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    config = load_auth_config()
    auth_config = config.get("auth", {})
    access_token_expires = timedelta(minutes=auth_config.get("access_token_expire_minutes", 30))
    refresh_token_expires = timedelta(days=auth_config.get("refresh_token_expire_days", 7))
    
    response.set_cookie(
        key="access_token",
        value=token_response.access_token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        path="/",
        max_age=int(access_token_expires.total_seconds())
    )
    
    response.set_cookie(
        key="refresh_token",
        value=token_response.refresh_token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        path="/",
        max_age=int(refresh_token_expires.total_seconds())
    )
    
    return token_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    token_data: Optional[RefreshTokenRequest] = None,
    db: Session = Depends(get_db)
):
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value and token_data:
        refresh_token_value = token_data.refresh_token
    
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided"
        )
    
    token_response = AuthService.refresh_access_token(db, RefreshTokenRequest(refresh_token=refresh_token_value))
    
    config = load_auth_config()
    auth_config = config.get("auth", {})
    access_token_expires = timedelta(minutes=auth_config.get("access_token_expire_minutes", 30))
    
    response.set_cookie(
        key="access_token",
        value=token_response.access_token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        path="/",
        max_age=int(access_token_expires.total_seconds())
    )
    
    if token_response.refresh_token != refresh_token_value:
        refresh_token_expires = timedelta(days=auth_config.get("refresh_token_expire_days", 7))
        response.set_cookie(
            key="refresh_token",
            value=token_response.refresh_token,
            httponly=True,
            secure=settings.SECURE_COOKIES,
            samesite="lax",
            path="/",
            max_age=int(refresh_token_expires.total_seconds())
        )
    
    return token_response


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    token_data: Optional[RefreshTokenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value and token_data:
        refresh_token_value = token_data.refresh_token
    
    if refresh_token_value:
        result = AuthService.logout_user(db, refresh_token_value, current_user.id)
    else:
        result = {"message": "Logged out successfully"}
    
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")
    
    return result


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return AuthService.get_current_user_info(current_user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return AuthService.get_current_user_info(user)

