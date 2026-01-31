"""Pydantic schemas for branding validation."""

from pydantic import BaseModel, Field
from typing import List, Literal


class ViolationSchema(BaseModel):
    """Represents a brand guideline violation."""
    rule: str = Field(..., description="Identificador da regra violada")
    category: str = Field(..., description="Categoria: colors, typography, logo, layout, cta, footer, prohibited")
    severity: Literal["critical", "warning", "info"] = Field(..., description="Severidade da violação")
    value: str = Field("", description="Valor que causou a violação")
    message: str = Field("", description="Mensagem descritiva da violação")


class ValidationSummary(BaseModel):
    """Summary of validation results."""
    critical: int = Field(..., description="Quantidade de violações críticas")
    warning: int = Field(..., description="Quantidade de warnings")
    info: int = Field(..., description="Quantidade de informações")
    total: int = Field(..., description="Total de violações")


class BrandValidationResult(BaseModel):
    """Result of brand validation."""
    compliant: bool = Field(..., description="Se está em conformidade (0 critical, 0 warning)")
    score: int = Field(..., ge=0, le=100, description="Pontuação 0-100")
    violations: List[ViolationSchema] = Field(default_factory=list, description="Lista de violações")
    summary: ValidationSummary = Field(..., description="Resumo das violações")


class BrandGuidelines(BaseModel):
    """Brand guidelines for reference."""
    colors: dict = Field(..., description="Paleta de cores aprovadas")
    typography: dict = Field(..., description="Regras de tipografia")
    logo: dict = Field(..., description="Regras do logo")
    layout: dict = Field(..., description="Regras de layout")
    cta: dict = Field(..., description="Regras de CTAs")
    footer: dict = Field(..., description="Regras de footer")
    prohibited: dict = Field(..., description="Elementos proibidos")
