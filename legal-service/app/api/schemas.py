import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Literal, Optional, Union


class ValidateRequestMetadata(BaseModel):
    """Metadados opcionais da requisição de validação."""
    transaction_id: Optional[str] = Field(None, description="ID da transação no sistema origem")
    timestamp: Optional[str] = Field(None, description="ISO 8601 da requisição")
    source_system: Optional[str] = Field(None, description="Sistema de origem (ex: CRM_FRONTEND)")


_DATA_URL_PATTERN = re.compile(
    r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=]+$"
)
_APP_IMAGE_MAX_BYTES = 1024 * 1024  # 1 MB (base64 payload)


class SMSContent(BaseModel):
    """Conteúdo para SMS (apenas body)."""
    body: str = Field(..., description="Corpo da mensagem SMS", min_length=1)


class PUSHContent(BaseModel):
    """Conteúdo para PUSH (title + body)."""
    title: str = Field(..., description="Título da notificação push", min_length=1)
    body: str = Field(..., description="Corpo da notificação push", min_length=1)


# Aumentado para suportar emails maiores (antes era 50_000)
EMAIL_HTML_MAX_LENGTH = 100_000


class EmailContent(BaseModel):
    """Conteúdo para EMAIL: pode ser HTML ou imagem (convertido via html-converter-service)."""
    
    # --- CÓDIGO LEGADO: apenas html era aceito ---
    # html: str = Field(..., description="Corpo HTML do e-mail", min_length=1, max_length=EMAIL_HTML_MAX_LENGTH)
    # --- FIM CÓDIGO LEGADO ---
    
    html: Optional[str] = Field(
        None,
        description="Corpo HTML do e-mail",
        min_length=1,
        max_length=EMAIL_HTML_MAX_LENGTH,
    )
    image: Optional[str] = Field(
        None,
        description="Imagem do e-mail renderizado (data URL base64, máx. 1 MB)",
        min_length=1,
    )

    @model_validator(mode='after')
    def validate_html_or_image(self):
        """Valida que pelo menos html OU image está presente."""
        if not self.html and not self.image:
            raise ValueError("Para channel=EMAIL, content deve ter 'html' ou 'image'")
        return self

    @field_validator("html")
    @classmethod
    def html_max_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > EMAIL_HTML_MAX_LENGTH:
            raise ValueError(
                f"O corpo HTML do e-mail excede o limite de {EMAIL_HTML_MAX_LENGTH:,} caracteres "
                f"(recebido: {len(v):,})."
            )
        return v

    @field_validator("image")
    @classmethod
    def image_data_url_and_size(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _DATA_URL_PATTERN.match(v):
            raise ValueError(
                "image deve ser data URL: data:image/<png|jpeg|jpg|webp|gif>;base64,<payload>"
            )
        idx = v.find(";base64,")
        if idx == -1:
            raise ValueError("image deve conter ';base64,'")
        payload = v[idx + 8:]
        size = len(payload.encode("utf-8"))
        if size > _APP_IMAGE_MAX_BYTES:
            raise ValueError(
                f"image excede 1 MB em base64 (recebido: {size / (1024*1024):.2f} MB)"
            )
        return v


class AppContent(BaseModel):
    """Conteúdo para APP (uma imagem em base64 data URL, até 1 MB). Sem download."""

    image: str = Field(
        ...,
        description="Imagem em data URL (data:image/<png|jpeg|jpg|webp|gif>;base64,...). Máx. 1 MB.",
        min_length=1,
    )

    @field_validator("image")
    @classmethod
    def image_data_url_and_size(cls, v: str) -> str:
        if not _DATA_URL_PATTERN.match(v):
            raise ValueError(
                "image deve ser data URL: data:image/<png|jpeg|jpg|webp|gif>;base64,<payload>"
            )
        idx = v.find(";base64,")
        if idx == -1:
            raise ValueError("image deve conter ';base64,'")
        payload = v[idx + 8:]
        size = len(payload.encode("utf-8"))
        if size > _APP_IMAGE_MAX_BYTES:
            raise ValueError(
                f"image excede 1 MB em base64 "
                f"(recebido: {size / (1024*1024):.2f} MB)"
            )
        return v


def _parse_content_by_channel(channel: str, content_data: dict) -> Union[SMSContent, PUSHContent, AppContent, EmailContent]:
    """Parseia content explicitamente baseado no channel (sem Union matching)."""
    if channel == "SMS":
        return SMSContent.model_validate(content_data)
    elif channel == "PUSH":
        return PUSHContent.model_validate(content_data)
    elif channel == "EMAIL":
        return EmailContent.model_validate(content_data)
    elif channel == "APP":
        return AppContent.model_validate(content_data)
    else:
        raise ValueError(f"Canal inválido: {channel}")


class ValidationInput(BaseModel):
    task: Literal["VALIDATE_COMMUNICATION"] = Field(..., description="Tipo de tarefa a ser executada")
    channel: Literal["SMS", "EMAIL", "PUSH", "APP"] = Field(..., description="Canal da comunicação")
    content: Union[SMSContent, PUSHContent, AppContent, EmailContent] = Field(
        ..., description="Conteúdo da comunicação a ser validado"
    )

    @model_validator(mode='before')
    @classmethod
    def parse_content_by_channel(cls, data):
        """Parseia content explicitamente baseado no channel, evitando Union matching."""
        if isinstance(data, dict):
            channel = data.get("channel")
            content = data.get("content")
            if channel and isinstance(content, dict):
                data["content"] = _parse_content_by_channel(channel, content)
        return data

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "task": "VALIDATE_COMMUNICATION",
                    "channel": "SMS",
                    "content": {"body": "Olá, Ana. O boleto de R$ 1.500,00 da sua Orqestra já está disponível."}
                },
                {
                    "task": "VALIDATE_COMMUNICATION",
                    "channel": "PUSH",
                    "content": {
                        "title": "Sua fatura chegou! 📑",
                        "body": "Olá, Ana. O boleto de R$ 1.500,00 da sua Orqestra já está disponível."
                    }
                },
                {
                    "task": "VALIDATE_COMMUNICATION",
                    "channel": "EMAIL",
                    "content": {
                        "html": "<html><body>...</body></html>"
                    }
                },
                {
                    "task": "VALIDATE_COMMUNICATION",
                    "channel": "APP",
                    "content": {
                        "image": "data:image/png;base64,iVBORw0KGgo..."
                    }
                }
            ]
        }


class ValidationOutput(BaseModel):
    decision: Literal["APROVADO", "REPROVADO"] = Field(..., description="Decisão final: APROVADO ou REPROVADO")
    requires_human_review: bool = Field(..., description="Indica se requer revisão humana (geralmente true quando REPROVADO)")
    summary: str = Field(..., description="Resumo claro e objetivo da análise e violações encontradas", min_length=1)
    sources: List[str] = Field(..., description="Lista de fontes (arquivos) utilizadas na análise", min_length=0)


class ValidateRequest(BaseModel):
    """Formato oficial da chamada de validação (POST /api/legal/validate)."""
    metadata: Optional[ValidateRequestMetadata] = Field(None, description="Metadados opcionais da requisição")
    task: Literal["VALIDATE_COMMUNICATION"] = Field(..., description="Tipo de tarefa a ser executada")
    channel: Literal["SMS", "EMAIL", "PUSH", "APP"] = Field(..., description="Canal da comunicação")
    payload_type: Literal["INLINE"] = Field(..., description="Tipo de payload; INLINE = conteúdo no body")
    content: Union[SMSContent, PUSHContent, AppContent, EmailContent] = Field(
        ..., description="Conteúdo da comunicação a ser validado"
    )

    @model_validator(mode="before")
    @classmethod
    def parse_content_by_channel(cls, data):
        """Parseia content explicitamente baseado no channel, evitando Union matching."""
        if isinstance(data, dict):
            channel = data.get("channel")
            content = data.get("content")
            if channel and isinstance(content, dict):
                data["content"] = _parse_content_by_channel(channel, content)
        return data

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "metadata": {
                        "transaction_id": "txn-sms-88210",
                        "timestamp": "2026-01-25T14:30:00Z",
                        "source_system": "CRM_FRONTEND",
                    },
                    "task": "VALIDATE_COMMUNICATION",
                    "channel": "SMS",
                    "payload_type": "INLINE",
                    "content": {
                        "body": "Orqestra - Ana, atualizamos as condições do seu Seguro Casa. Confira no app para saber mais. SAIR para cancelar.",
                    },
                },
            ],
        },
    }

