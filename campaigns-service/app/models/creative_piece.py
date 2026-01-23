from sqlalchemy import Column, String, DateTime, ForeignKey, Text, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class CreativePieceType(str, enum.Enum):
    SMS = "SMS"
    PUSH = "Push"
    APP = "App"
    EMAIL = "E-mail"


class CreativePiece(Base):
    __tablename__ = "creative_pieces"
    
    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    piece_type = Column(String, nullable=False)
    text = Column(Text, nullable=True)
    title = Column(String, nullable=True) 
    body = Column(Text, nullable=True) 
    file_urls = Column(Text, nullable=True)  
    html_file_url = Column(String, nullable=True)  
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    campaign = relationship("Campaign", back_populates="creative_pieces")

