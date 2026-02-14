from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class AIInteraction(Base):    
    __tablename__ = "audit_interactions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    user_id = Column(String, nullable=False, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    llm_model = Column(String, nullable=True)
    session_id = Column(String, nullable=True, index=True)
    user_decision = Column(String(20), nullable=True, index=True)
    decision_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_audit_interactions_user_campaign", "user_id", "campaign_id"),
        Index("ix_audit_interactions_session", "session_id"),
        Index("ix_audit_interactions_created_at", "created_at"),
    )
    
    def __repr__(self):
        return f"<AIInteraction(id='{self.id}', user_id='{self.user_id}', field_name='{self.field_name}', created_at='{self.created_at}')>"

