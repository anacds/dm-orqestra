"""Immutable audit log of piece review lifecycle events."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from app.core.database import Base


class PieceReviewEventType(str, enum.Enum):
    SUBMITTED = "SUBMITTED"  # Analista de criação submeteu para revisão
    APPROVED = "APPROVED"  # Analista de arte aprovou
    REJECTED = "REJECTED"  # Analista de arte rejeitou (confirmando IA)
    MANUALLY_REJECTED = "MANUALLY_REJECTED"  # Analista de arte rejeitou (override da IA)


class PieceReviewEvent(Base):
    """
    Registro imutável de eventos no ciclo de revisão de peças.
    
    Esta tabela é append-only: nunca atualiza ou deleta registros.
    O histórico completo pode ser reconstruído ordenando por created_at.
    """
    __tablename__ = "piece_review_event"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(
        String, 
        ForeignKey("campaigns.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Identificação da peça
    channel = Column(String, nullable=False)  # SMS | PUSH | EMAIL | APP
    piece_id = Column(String, nullable=False)
    commercial_space = Column(String, nullable=False, default="")  # Só para APP
    
    # O que aconteceu
    event_type = Column(String, nullable=False)
    
    # Contexto do evento (depende do event_type)
    ia_verdict = Column(String, nullable=True)  # Só para SUBMITTED
    rejection_reason = Column(Text, nullable=True)  # Só para REJECTED/MANUALLY_REJECTED
    
    # Quem fez
    actor_id = Column(String, nullable=False)
    
    # Quando
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    __table_args__ = (
        Index(
            'ix_piece_review_event_piece_lookup',
            'campaign_id',
            'channel',
            'piece_id',
            'commercial_space',
        ),
    )
