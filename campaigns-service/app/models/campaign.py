from sqlalchemy import Column, String, DateTime, Integer, Enum as SQLEnum, ARRAY, ForeignKey, Date, Numeric, TypeDecorator
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from decimal import Decimal
from typing import Type, TypeVar
from app.core.database import Base

EnumType = TypeVar('EnumType', bound=enum.Enum)

class EnumValueType(TypeDecorator):
    impl = String
    cache_ok = True
    
    def __init__(self, enum_class: Type[EnumType], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_class = enum_class
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        return value
    
    def process_result_value(self, value, dialect):
        if value is None:
            return None

        for member in self.enum_class:
            if member.value == value:
                return member

        raise ValueError(f"Invalid value '{value}' for enum {self.enum_class.__name__}")


class CampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"  # Rascunho
    CREATIVE_STAGE = "CREATIVE_STAGE"  # Etapa Criativa
    CONTENT_REVIEW = "CONTENT_REVIEW"  # Conteúdo em Revisão
    CONTENT_ADJUSTMENT = "CONTENT_ADJUSTMENT"  # Ajuste de Conteúdo
    CAMPAIGN_BUILDING = "CAMPAIGN_BUILDING"  # Campanha em Construção
    CAMPAIGN_PUBLISHED = "CAMPAIGN_PUBLISHED"  # Campanha Publicada


class CampaignCategory(str, enum.Enum):
    ACQUISITION = "Aquisição"
    CROSS_SELL = "Cross-sell"
    UPSELL = "Upsell"
    RETENTION = "Retenção"
    RELATIONSHIP = "Relacionamento"
    REGULATORY = "Regulatório"
    EDUCATIONAL = "Educacional"


class RequestingArea(str, enum.Enum):
    PRODUCTS_PF = "Produtos PF"
    PRODUCTS_PJ = "Produtos PJ"
    COMPLIANCE = "Compliance"
    DIGITAL_CHANNELS = "Canais Digitais"
    INSTITUTIONAL_MARKETING = "Marketing Institucional"


class CampaignPriority(str, enum.Enum):
    NORMAL = "Normal"
    HIGH = "Alta"
    REGULATORY_OBLIGATORY = "Regulatório / Obrigatório"


class CommunicationChannel(str, enum.Enum):
    SMS = "SMS"
    PUSH = "Push"
    EMAIL = "E-mail"
    APP = "App"


class CommercialSpace(str, enum.Enum):
    HOME_BANNER = "Banner superior da Home"
    CLIENT_AREA = "Área do Cliente"
    OFFERS_PAGE = "Página de ofertas"
    PIX_RECEIPT = "Comprovante do Pix"


class CommunicationTone(str, enum.Enum):
    FORMAL = "Formal"
    INFORMAL = "Informal"
    URGENT = "Urgente"
    EDUCATIONAL = "Educativo"
    CONSULTIVE = "Consultivo"


class ExecutionModel(str, enum.Enum):
    BATCH = "Batch (agendada)"
    EVENT_DRIVEN = "Event-driven (por evento)"


class TriggerEvent(str, enum.Enum):
    BILL_CLOSED = "Fatura fechada"
    CARD_LIMIT_EXCEEDED = "Cliente ultrapassa limite do cartão"
    APP_LOGIN = "Login no app"
    INACTIVITY_30_DAYS = "Inatividade por 30 dias"


class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(EnumValueType(CampaignCategory), nullable=False)
    business_objective = Column(String, nullable=False)
    expected_result = Column(String, nullable=False)
    requesting_area = Column(EnumValueType(RequestingArea), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    priority = Column(EnumValueType(CampaignPriority), nullable=False)
    communication_channels = Column(ARRAY(String), nullable=False)
    commercial_spaces = Column(ARRAY(String), nullable=True)  # Only if App is selected
    target_audience_description = Column(String, nullable=False)
    exclusion_criteria = Column(String, nullable=False)
    estimated_impact_volume = Column(Numeric(12, 2), nullable=False)  # Monetary value in BRL
    communication_tone = Column(EnumValueType(CommunicationTone), nullable=False)
    execution_model = Column(EnumValueType(ExecutionModel), nullable=False)
    trigger_event = Column(EnumValueType(TriggerEvent), nullable=True)  # Only if Event-driven
    recency_rule_days = Column(Integer, nullable=False)
    status = Column(EnumValueType(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False)
    created_by = Column(String, nullable=False)
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    comments = relationship("Comment", back_populates="campaign", cascade="all, delete-orphan")
    creative_pieces = relationship("CreativePiece", back_populates="campaign", cascade="all, delete-orphan")
