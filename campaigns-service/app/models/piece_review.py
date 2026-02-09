"""Per-piece review state (IA verdict snapshot + human verdict) for CONTENT_REVIEW workflow."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from app.core.database import Base


class IaVerdict(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"


class HumanVerdict(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUALLY_REJECTED = "manually_rejected"


class PieceReview(Base):
    """One row per reviewable unit: SMS/Push/Email = 1 per piece; App = 1 per (piece, commercial_space)."""

    __tablename__ = "piece_review"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)  # SMS | PUSH | EMAIL | APP
    piece_id = Column(String, nullable=False, index=True)
    commercial_space = Column(String, nullable=False, default="")  # "" for non-App
    ia_verdict = Column(String, nullable=True)  # approved | rejected | null (não validado)
    human_verdict = Column(String, nullable=False, default=HumanVerdict.PENDING.value)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_piece_review_lookup",
            "campaign_id",
            "channel",
            "piece_id",
            "commercial_space",
            unique=True,
        ),
    )
