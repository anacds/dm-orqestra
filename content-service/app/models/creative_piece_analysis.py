from sqlalchemy import Column, String, DateTime, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


class CreativePieceAnalysis(Base):
    __tablename__ = "creative_piece_analyses"
    
    id = Column(String, primary_key=True)
    campaign_id = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # "SMS" or "Push"
    content_hash = Column(String, nullable=False)  # Hash of the piece content to detect changes
    
    # Analysis result
    is_valid = Column(String, nullable=False)  # "valid" | "invalid" | "warning"
    analysis_text = Column(Text, nullable=False)  # Detailed analysis/comments
    
    # Metadata
    analyzed_by = Column(String, nullable=False)  # User ID who requested the analysis
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes for fast lookup
    __table_args__ = (
        Index("ix_creative_piece_analysis_campaign_channel", "campaign_id", "channel"),
        Index("ix_creative_piece_analysis_content_hash", "content_hash"),
        {},
    )

