from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ARRAY, Index
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
import hashlib


class LegalValidationAudit(Base):
    __tablename__ = "legal_validation_audits"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)
    task = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)
    content_hash = Column(String, index=True)
    
    content_preview = Column(String(500))
    
    decision = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False, index=True)
    requires_human_review = Column(Boolean, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    sources = Column(ARRAY(String))
    
    num_chunks_retrieved = Column(Integer)
    llm_model = Column(String)
    search_query = Column(String(1000))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    __table_args__ = (
        Index("ix_legal_validation_audits_channel_decision", "channel", "decision"),
        Index("ix_legal_validation_audits_created_at", "created_at"),
        Index("ix_legal_validation_audits_content_hash", "content_hash"),
    )
    
    def __repr__(self):
        return f"<LegalValidationAudit(id='{self.id}', channel='{self.channel}', decision='{self.decision}', created_at='{self.created_at}')>"
    
    @staticmethod
    def generate_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

