from __future__ import annotations

import hashlib
import uuid
from sqlalchemy import Column, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


def content_hash_sms(body: str | None) -> str:
    """Same algorithm as frontend calculateContentHash for SMS."""
    s = f"SMS:{body or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_hash_push(title: str | None, body: str | None) -> str:
    """Same algorithm as frontend calculateContentHash for Push."""
    s = f"Push:{title or ''}:{body or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_hash_email(piece_id: str) -> str:
    """Lookup key for Email validation cache (campaign_id + piece_id)."""
    s = f"EMAIL:{piece_id or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def content_hash_app(piece_id: str, commercial_space: str) -> str:
    """Lookup key for App validation cache (one row per space)."""
    s = f"APP:{piece_id or ''}:{commercial_space or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class PieceValidationCache(Base):
    __tablename__ = "piece_validation_cache"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, index=True)  # SMS | PUSH | EMAIL | APP
    content_hash = Column(String, nullable=False, index=True)
    response_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_piece_validation_cache_lookup",
            "campaign_id",
            "channel",
            "content_hash",
            unique=True,
        ),
    )
