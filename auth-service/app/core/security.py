from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import secrets
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.auth_config import load_auth_config
from app.core.database import get_db
from app.models.user import User

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for password."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        config = load_auth_config()
        auth_config = config.get("auth", {})
        expire_minutes = auth_config.get("access_token_expire_minutes", 30)
        expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    config = load_auth_config()
    auth_config = config.get("auth", {})
    algorithm = auth_config.get("algorithm", "HS256")
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=algorithm)
    return encoded_jwt

def create_refresh_token() -> str:
    """Generate secure refresh token."""
    return secrets.token_urlsafe(32)

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate JWT access token."""
    try:
        config = load_auth_config()
        auth_config = config.get("auth", {})
        algorithm = auth_config.get("algorithm", "HS256")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def get_token_from_cookie_or_header(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> str:
    """Extract access token from cookie or Authorization header."""
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    
    if token:
        return token
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    token: str = Depends(get_token_from_cookie_or_header),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user

