"""Especificações técnicas por canal e espaço comercial.

Cada registro define limites de dimensão, peso e caracteres para um
canal (SMS, PUSH, EMAIL, APP) e opcionalmente um espaço comercial.
Gerenciável via banco — sem necessidade de deploy para novos formatos.
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class ChannelSpec(Base):
    """Specs técnicos de um canal/espaço comercial."""

    __tablename__ = "channel_specs"

    id = Column(String, primary_key=True)
    channel = Column(String, nullable=False, index=True)  # SMS | PUSH | EMAIL | APP
    commercial_space = Column(String, nullable=True, index=True)  # NULL = spec genérico do canal
    field_name = Column(String, nullable=False)  # body, title, html, image, rendered_image

    # Limites de caracteres
    min_chars = Column(Integer, nullable=True)
    max_chars = Column(Integer, nullable=True)
    warn_chars = Column(Integer, nullable=True)

    # Limites de peso (KB)
    max_weight_kb = Column(Integer, nullable=True)

    # Limites de dimensão (pixels)
    min_width = Column(Integer, nullable=True)
    min_height = Column(Integer, nullable=True)
    max_width = Column(Integer, nullable=True)
    max_height = Column(Integer, nullable=True)
    expected_width = Column(Integer, nullable=True)  # Dimensão ideal (para espaços comerciais)
    expected_height = Column(Integer, nullable=True)
    tolerance_pct = Column(Integer, nullable=True, default=5)  # % de tolerância nas dimensões

    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
