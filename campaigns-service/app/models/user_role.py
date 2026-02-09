import enum

class UserRole(str, enum.Enum):
    BUSINESS_ANALYST = "Analista de negócios"
    CREATIVE_ANALYST = "Analista de criação"
    CAMPAIGN_ANALYST = "Analista de campanhas"
    MARKETING_MANAGER = "Gestor de marketing"
