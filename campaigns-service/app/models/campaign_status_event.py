from __future__ import annotations

import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from app.core.database import Base


class CampaignStatusEvent(Base):
    """
    Registro de transições de status da campanha.
    
    Esta tabela é append-only: nunca atualiza ou deleta registros.
    O histórico completo pode ser reconstruído ordenando por created_at.
    """
    __tablename__ = "campaign_status_event"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(
        String, 
        ForeignKey("campaigns.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Status anterior (None para criação inicial)
    from_status = Column(String, nullable=True)
    
    # Novo status
    to_status = Column(String, nullable=False)
    
    # Quem fez a transição
    actor_id = Column(String, nullable=False)
    
    # Quando
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    __table_args__ = (
        Index('ix_campaign_status_event_campaign_created', 'campaign_id', 'created_at'),
    )
