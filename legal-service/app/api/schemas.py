from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional, Union


class SMSContent(BaseModel):
    """Conteúdo para SMS (apenas body)."""
    body: str = Field(..., description="Corpo da mensagem SMS", min_length=1)


class PUSHContent(BaseModel):
    """Conteúdo para PUSH (title + body)."""
    title: str = Field(..., description="Título da notificação push", min_length=1)
    body: str = Field(..., description="Corpo da notificação push", min_length=1)


class ValidationInput(BaseModel):
    task: Literal["VALIDATE_COMMUNICATION"] = Field(..., description="Tipo de tarefa a ser executada")
    channel: Literal["SMS", "EMAIL", "PUSH", "APP"] = Field(..., description="Canal da comunicação")
    content: Union[SMSContent, PUSHContent] = Field(..., description="Conteúdo da comunicação a ser validado")
    
    @model_validator(mode='after')
    def validate_content_channel(self):
        """Valida que o formato de content corresponde ao channel."""
        if self.channel == "PUSH":
            if not isinstance(self.content, PUSHContent):
                raise ValueError("Para channel=PUSH, content deve ter 'title' e 'body'")
        elif self.channel == "SMS":
            if not isinstance(self.content, SMSContent):
                raise ValueError("Para channel=SMS, content deve ter apenas 'body'")
        # EMAIL e APP podem usar qualquer formato por enquanto
        return self
    
    class Config:
        # Permite que Pydantic discrimine entre SMSContent e PUSHContent
        # baseado na presença de 'title'
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
                }
            ]
        }


class ValidationOutput(BaseModel):
    decision: Literal["APROVADO", "REPROVADO"] = Field(..., description="Decisão final: APROVADO ou REPROVADO")
    severity: Literal["BLOCKER", "WARNING", "INFO"] = Field(..., description="Severidade: BLOCKER (bloqueia), WARNING (atenção), INFO (aprovado com observações)")
    requires_human_review: bool = Field(..., description="Indica se requer revisão humana (geralmente true para BLOCKER e WARNING críticos)")
    summary: str = Field(..., description="Resumo claro e objetivo da análise e violações encontradas", min_length=1)
    sources: List[str] = Field(..., description="Lista de fontes (arquivos) utilizadas na análise", min_items=0)

