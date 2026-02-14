"""Audit table for piece validation results (permanent log in PostgreSQL)."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class PieceValidationAudit(Base):
    """Permanent audit log of every piece validation executed."""

    __tablename__ = "piece_validation_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)  # SMS | PUSH | EMAIL | APP
    content_hash = Column(String, nullable=False, index=True)
    response_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_piece_validation_audit_lookup",
            "campaign_id",
            "channel",
            "content_hash",
        ),
        Index(
            "ix_piece_validation_audit_created_at",
            "created_at",
        ),
    )
