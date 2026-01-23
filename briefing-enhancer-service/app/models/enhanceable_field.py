from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class EnhanceableField(Base):
    __tablename__ = "enhanceable_fields"
    
    field_name = Column(String(100), primary_key=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    expectations = Column(Text, nullable=False)
    improvement_guidelines = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<EnhanceableField(field_name='{self.field_name}', display_name='{self.display_name}')>"

