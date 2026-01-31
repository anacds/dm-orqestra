"""Valida formato e tamanho da peça antes de enviar ao legal-service.

Regras alinhadas ao legal-service:
- SMS: body (min 1 char)
- PUSH: title + body (min 1 cada)
- EMAIL: html (min 1 char; máx 50_000 chars; frontend não coleta assunto)
- APP: image (data URL base64, máx 1 MB)
"""

from __future__ import annotations

import json
import re
from typing import Any

EMAIL_HTML_MAX_LENGTH = 50_000
APP_IMAGE_MAX_BYTES = 1024 * 1024  # 1 MB
_DATA_URL_PATTERN = re.compile(
    r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=]+$"
)


def validate_piece_format_and_size(
    channel: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """Valida formato e tamanho da peça de comunicação.

    Args:
        channel: Canal da peça (SMS, PUSH, EMAIL ou APP).
        content: Conteúdo da peça (dict). Estrutura esperada por canal:
            - SMS: {"body": str}
            - PUSH: {"title": str, "body": str}
            - EMAIL: {"html": str}
            - APP: {"image": str} (data URL base64)

    Returns:
        Dict com valid, message, errors, details.
    """
    errors: list[str] = []
    details: dict[str, Any] = {"channel": channel}

    if channel not in ("SMS", "PUSH", "EMAIL", "APP"):
        return {
            "valid": False,
            "message": f"Canal inválido: {channel}. Use SMS, PUSH, EMAIL ou APP.",
            "errors": [f"Canal inválido: {channel}"],
            "details": details,
        }

    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "message": "content deve ser um objeto JSON válido.",
                "errors": [f"JSON inválido em content: {e}"],
                "details": details,
            }
    if not isinstance(content, dict):
        return {
            "valid": False,
            "message": "content deve ser um objeto JSON.",
            "errors": ["content deve ser um objeto (dict)."],
            "details": details,
        }

    if channel == "SMS":
        _validate_sms(content, errors, details)
    elif channel == "PUSH":
        _validate_push(content, errors, details)
    elif channel == "EMAIL":
        _validate_email(content, errors, details)
    elif channel == "APP":
        _validate_app(content, errors, details)

    if errors:
        return {
            "valid": False,
            "message": "Formato ou tamanho inválido: " + "; ".join(errors[:3]),
            "errors": errors,
            "details": details,
        }

    return {
        "valid": True,
        "message": f"Formato e tamanho OK para {channel}.",
        "errors": None,
        "details": details,
    }


def _validate_sms(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    if "body" not in content:
        errors.append("Para channel=SMS, content deve ter 'body'.")
        return
    body = content["body"]
    if not isinstance(body, str):
        errors.append("content.body deve ser string.")
        return
    if len(body.strip()) < 1:
        errors.append("content.body não pode ser vazio.")
        return
    details["body_length"] = len(body)


def _validate_push(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    for key in ("title", "body"):
        if key not in content:
            errors.append(f"Para channel=PUSH, content deve ter '{key}'.")
            continue
        v = content[key]
        if not isinstance(v, str):
            errors.append(f"content.{key} deve ser string.")
        elif len(v.strip()) < 1:
            errors.append(f"content.{key} não pode ser vazio.")
    if "title" in content and isinstance(content["title"], str):
        details["title_length"] = len(content["title"])
    if "body" in content and isinstance(content["body"], str):
        details["body_length"] = len(content["body"])


def _validate_email(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    if "html" not in content:
        errors.append("Para channel=EMAIL, content deve ter 'html'.")
        return
    v = content["html"]
    if not isinstance(v, str):
        errors.append("content.html deve ser string.")
        return
    if len(v.strip()) < 1:
        errors.append("content.html não pode ser vazio.")
        return
    n = len(v)
    details["html_length"] = n
    details["html_max"] = EMAIL_HTML_MAX_LENGTH
    if n > EMAIL_HTML_MAX_LENGTH:
        errors.append(
            f"content.html excede {EMAIL_HTML_MAX_LENGTH:,} caracteres (recebido: {n:,})."
        )


def _validate_app(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    if "image" not in content:
        errors.append("Para channel=APP, content deve ter 'image' (data URL base64, máx. 1 MB).")
        return
    img = content["image"]
    if not isinstance(img, str):
        errors.append("content.image deve ser string (data URL).")
        return
    if not _DATA_URL_PATTERN.match(img):
        errors.append(
            "content.image deve ser data URL: data:image/<png|jpeg|jpg|webp|gif>;base64,<payload>"
        )
        return
    idx = img.find(";base64,")
    if idx == -1:
        errors.append("content.image deve conter ';base64,'.")
        return
    payload = img[idx + 8 :]
    size = len(payload.encode("utf-8"))
    details["image_size_bytes"] = size
    details["image_max_bytes"] = APP_IMAGE_MAX_BYTES
    if size > APP_IMAGE_MAX_BYTES:
        errors.append(
            f"content.image excede 1 MB em base64 (recebido: {size / (1024*1024):.2f} MB)."
        )


if __name__ == "__main__":
    r = validate_piece_format_and_size("SMS", {"body": "Olá, teste."})
    assert r["valid"] and "OK" in r["message"], r
    r = validate_piece_format_and_size("SMS", {})
    assert not r["valid"] and "body" in r["errors"][0], r
    r = validate_piece_format_and_size("EMAIL", {"html": "a" * 60_000})
    assert not r["valid"] and "50" in r["errors"][0], r
    r = validate_piece_format_and_size("APP", {"image": "not-a-data-url"})
    assert not r["valid"] and "data URL" in r["errors"][0], r
    print("validate_piece_format_and_size OK")
