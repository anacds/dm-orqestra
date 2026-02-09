from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    BUSINESS_ANALYST = "Analista de negócios"
    CREATIVE_ANALYST = "Analista de criação"
    CAMPAIGN_ANALYST = "Analista de campanhas"
    MARKETING_MANAGER = "Gestor de marketing"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

