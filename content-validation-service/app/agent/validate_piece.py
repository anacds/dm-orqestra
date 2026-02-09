"""Validação determinística de peças de comunicação.

Dois níveis de validação:
1. validate_piece_format_and_size — gate-keeping básico (formato, presença de campos).
   Executado no validate_channel_node ANTES de retrieve.
2. validate_piece_specs — validação de specs técnicos (dimensões, peso, qtde de chars).
   Executado no validate_specs_node DEPOIS do retrieve, usando channel_specs.yaml.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Carrega specs do YAML
# ---------------------------------------------------------------------------
_SPECS_PATH = os.environ.get(
    "CHANNEL_SPECS_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "config" / "channel_specs.yaml"),
)

_channel_specs: dict[str, Any] | None = None


def _load_specs() -> dict[str, Any]:
    """Carrega e cacheia channel_specs.yaml."""
    global _channel_specs
    if _channel_specs is not None:
        return _channel_specs
    try:
        with open(_SPECS_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        _channel_specs = raw.get("channels", {})
        logger.info("channel_specs.yaml loaded from %s (%d channels)", _SPECS_PATH, len(_channel_specs))
    except Exception as e:
        logger.warning("Failed to load channel_specs.yaml from %s: %s — using defaults", _SPECS_PATH, e)
        _channel_specs = {}
    return _channel_specs


def get_channel_specs(channel: str) -> dict[str, Any]:
    """Retorna specs para um canal específico."""
    specs = _load_specs()
    return specs.get(channel.upper(), {})


# ---------------------------------------------------------------------------
# Padrão de data URL para validação de estrutura (APP)
# ---------------------------------------------------------------------------
_DATA_URL_PATTERN = re.compile(
    r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=]+$"
)


# ===========================================================================
# NÍVEL 1: Validação de estrutura (antes do retrieve)
#
# Responsabilidade: canal reconhecido? campos obrigatórios existem? tipos corretos?
# NÃO verifica limites numéricos (chars, KB, pixels) — isso é do validate_specs.
# ===========================================================================

def validate_piece_format_and_size(
    channel: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """Valida estrutura e presença dos campos obrigatórios.

    Verifica APENAS:
    - Canal é reconhecido
    - Content é dict válido
    - Campos obrigatórios existem e são do tipo correto

    Limites numéricos (chars, KB, pixels) ficam em validate_piece_specs.

    Args:
        channel: Canal da peça (SMS, PUSH, EMAIL ou APP).
        content: Conteúdo da peça (dict).

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
        _validate_sms_structure(content, errors, details)
    elif channel == "PUSH":
        _validate_push_structure(content, errors, details)
    elif channel == "EMAIL":
        _validate_email_structure(content, errors, details)
    elif channel == "APP":
        _validate_app_structure(content, errors, details)

    if errors:
        return {
            "valid": False,
            "message": "Estrutura inválida: " + "; ".join(errors[:3]),
            "errors": errors,
            "details": details,
        }

    return {
        "valid": True,
        "message": f"Estrutura OK para {channel}.",
        "errors": None,
        "details": details,
    }


def _validate_sms_structure(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    """SMS: campo 'body' existe e é string."""
    if "body" not in content:
        errors.append("Para channel=SMS, content deve ter 'body'.")
        return
    if not isinstance(content["body"], str):
        errors.append("content.body deve ser string.")


def _validate_push_structure(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    """PUSH: campos 'title' e 'body' existem e são strings."""
    for key in ("title", "body"):
        if key not in content:
            errors.append(f"Para channel=PUSH, content deve ter '{key}'.")
            continue
        if not isinstance(content[key], str):
            errors.append(f"content.{key} deve ser string.")


def _validate_email_structure(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    """EMAIL inline: campo 'html' existe e é string. (Usado raramente — EMAIL normalmente vai por retrieve.)"""
    if "html" not in content:
        errors.append("Para channel=EMAIL, content deve ter 'html'.")
        return
    if not isinstance(content["html"], str):
        errors.append("content.html deve ser string.")


def _validate_app_structure(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    """APP inline: campo 'image' existe, é string e tem formato data URL válido."""
    if "image" not in content:
        errors.append("Para channel=APP, content deve ter 'image' (data URL base64).")
        return
    img = content["image"]
    if not isinstance(img, str):
        errors.append("content.image deve ser string (data URL).")
        return
    if not _DATA_URL_PATTERN.match(img):
        errors.append(
            "content.image deve ser data URL: data:image/<png|jpeg|jpg|webp|gif>;base64,<payload>"
        )


# ===========================================================================
# NÍVEL 2: Validação de specs técnicos (após retrieve)
# ===========================================================================

def validate_piece_specs(
    channel: str,
    content: dict[str, Any],
    commercial_space: Optional[str] = None,
    conversion_metadata: Optional[dict[str, Any]] = None,
    remote_specs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Valida specs técnicos da peça (dimensões, peso, caracteres).

    Executado APÓS o retrieve_content_node, quando o conteúdo real já está disponível.

    Args:
        channel: Canal (SMS, PUSH, EMAIL, APP).
        content: Conteúdo real da peça.
        commercial_space: Espaço comercial (para APP).
        conversion_metadata: Metadados da conversão HTML->imagem (EMAIL).
        remote_specs: Specs obtidos via MCP (campaigns-service).
            Formato: {"specs": {"field_name": {...}}, "generic_specs": {"field_name": {...}}}
            Se None, usa fallback do channel_specs.yaml local.

    Returns:
        Dict com valid, errors, warnings, details.
    """
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {"channel": channel, "specs_source": "remote" if remote_specs else "local"}

    # Resolve specs: remote (MCP) > local (YAML)
    if remote_specs and remote_specs.get("specs"):
        specs_by_field = remote_specs["specs"]
        generic_by_field = remote_specs.get("generic_specs", {})
    else:
        # Fallback para YAML local
        local = get_channel_specs(channel)
        specs_by_field = _local_specs_to_field_dict(channel, local, commercial_space)
        generic_by_field = _local_specs_to_field_dict(channel, local, None)

    if channel == "SMS":
        _validate_sms_specs(content, specs_by_field, errors, warnings, details)
    elif channel == "PUSH":
        _validate_push_specs(content, specs_by_field, errors, warnings, details)
    elif channel == "EMAIL":
        _validate_email_specs(content, specs_by_field, conversion_metadata, errors, warnings, details)
    elif channel == "APP":
        _validate_app_specs_v2(content, specs_by_field, generic_by_field, commercial_space, errors, warnings, details)

    valid = len(errors) == 0

    message_parts = []
    if errors:
        message_parts.append(f"{len(errors)} erro(s)")
    if warnings:
        message_parts.append(f"{len(warnings)} aviso(s)")
    if not message_parts:
        message_parts.append("OK")

    return {
        "valid": valid,
        "message": f"Specs {channel}: " + ", ".join(message_parts),
        "errors": errors if errors else None,
        "warnings": warnings if warnings else None,
        "details": details,
    }


def _local_specs_to_field_dict(
    channel: str,
    local_specs: dict[str, Any],
    commercial_space: Optional[str],
) -> dict[str, dict[str, Any]]:
    """Converte specs do YAML local para o formato field_name -> {attrs} compatível com remote."""
    result: dict[str, dict[str, Any]] = {}

    if channel == "SMS":
        body_specs = local_specs.get("body", {})
        if body_specs:
            result["body"] = body_specs
    elif channel == "PUSH":
        for field in ("title", "body"):
            field_specs = local_specs.get(field, {})
            if field_specs:
                result[field] = field_specs
    elif channel == "EMAIL":
        for field in ("html", "rendered_image"):
            field_specs = local_specs.get(field, {})
            if field_specs:
                result[field] = field_specs
    elif channel == "APP":
        image_specs = local_specs.get("image", {})
        if image_specs:
            result["image"] = image_specs
        # Merge espaço comercial se disponível
        if commercial_space:
            space_key = commercial_space.strip().lower().replace(" ", "_")
            space_map = local_specs.get("commercial_spaces", {})
            space_data = space_map.get(space_key, {})
            if space_data:
                result["image"] = {**result.get("image", {}), **space_data}

    return result


# ---------------------------------------------------------------------------
# SMS specs
# ---------------------------------------------------------------------------

def _validate_sms_specs(
    content: dict[str, Any],
    specs: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    body = content.get("body", "")
    if not isinstance(body, str):
        return

    body_specs = specs.get("body", {})
    min_chars = body_specs.get("min_chars", 1)
    max_chars = body_specs.get("max_chars", 160)
    char_count = len(body)

    details["body_chars"] = char_count
    details["max_chars"] = max_chars

    if char_count < min_chars:
        errors.append(f"SMS vazio. Mínimo: {min_chars} caractere(s).")
    elif char_count > max_chars:
        errors.append(
            f"SMS excede o limite de {max_chars} caracteres."
        )


# ---------------------------------------------------------------------------
# PUSH specs
# ---------------------------------------------------------------------------

def _validate_push_specs(
    content: dict[str, Any],
    specs: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    title = content.get("title", "")
    body = content.get("body", "")

    title_specs = specs.get("title", {})
    body_specs = specs.get("body", {})

    title_max = title_specs.get("max_chars", 50)
    body_max = body_specs.get("max_chars", 150)

    if isinstance(title, str):
        title_len = len(title)
        details["title_chars"] = title_len
        details["title_max_chars"] = title_max
        if title_len > title_max:
            errors.append(
                f"Título do Push excede {title_max} caracteres (recebido: {title_len}). "
                "Pode ser truncado em dispositivos móveis."
            )

    if isinstance(body, str):
        body_len = len(body)
        details["body_chars"] = body_len
        details["body_max_chars"] = body_max
        if body_len > body_max:
            errors.append(
                f"Corpo do Push excede {body_max} caracteres (recebido: {body_len}). "
                "Pode ser truncado em dispositivos móveis."
            )


# ---------------------------------------------------------------------------
# EMAIL specs
# ---------------------------------------------------------------------------

def _validate_email_specs(
    content: dict[str, Any],
    specs: dict[str, Any],
    conversion_metadata: Optional[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    html = content.get("html", "")
    html_specs = specs.get("html", {})
    rendered_specs = specs.get("rendered_image", {})

    # Peso do HTML (em KB)
    if isinstance(html, str) and html:
        html_weight_kb = len(html.encode("utf-8")) / 1024
        max_weight_kb = html_specs.get("max_weight_kb", 100)

        details["html_weight_kb"] = round(html_weight_kb, 1)
        details["html_max_weight_kb"] = max_weight_kb

        if html_weight_kb > max_weight_kb:
            errors.append(
                f"HTML do email pesa {html_weight_kb:.1f} KB (máximo: {max_weight_kb} KB). "
                "Emails pesados podem ser cortados por clientes de email (Gmail corta em ~102 KB)."
            )

    # Metadados da imagem renderizada (se disponíveis)
    if conversion_metadata:
        rendered_max_kb = rendered_specs.get("max_weight_kb", 500)
        file_size_bytes = conversion_metadata.get("fileSizeBytes", 0)
        file_size_kb = file_size_bytes / 1024 if file_size_bytes else 0

        original_width = conversion_metadata.get("originalWidth", 0)
        original_height = conversion_metadata.get("originalHeight", 0)

        details["rendered_width"] = original_width
        details["rendered_height"] = original_height
        details["rendered_weight_kb"] = round(file_size_kb, 1)
        details["rendered_max_weight_kb"] = rendered_max_kb

        if file_size_kb > rendered_max_kb:
            warnings.append(
                f"Imagem renderizada do email pesa {file_size_kb:.1f} KB "
                f"(máximo recomendado: {rendered_max_kb} KB)."
            )


# ---------------------------------------------------------------------------
# APP specs (v2 — compatível com remote_specs do MCP)
# ---------------------------------------------------------------------------

def _validate_app_specs_v2(
    content: dict[str, Any],
    specs_by_field: dict[str, dict[str, Any]],
    generic_by_field: dict[str, dict[str, Any]],
    commercial_space: Optional[str],
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    """Valida specs de imagem APP usando formato field_name -> {attrs}.

    specs_by_field: specs específicos (do espaço comercial, se disponível).
    generic_by_field: specs genéricos do canal APP (fallback).
    """
    image_data = content.get("image", "")
    if not isinstance(image_data, str) or not image_data:
        return

    image_specs = specs_by_field.get("image", {})
    generic_specs = generic_by_field.get("image", {})

    # Peso da imagem
    max_weight_kb = image_specs.get("max_weight_kb", generic_specs.get("max_weight_kb", 1024))

    image_bytes = _decode_image_bytes(image_data)
    if image_bytes is None:
        errors.append("Não foi possível decodificar a imagem APP.")
        return

    weight_kb = len(image_bytes) / 1024
    details["image_weight_kb"] = round(weight_kb, 1)
    details["image_max_weight_kb"] = max_weight_kb

    if weight_kb > max_weight_kb:
        errors.append(
            f"Imagem APP pesa {weight_kb:.1f} KB (máximo: {max_weight_kb} KB)."
        )

    # Dimensões da imagem
    dimensions = _get_image_dimensions(image_bytes)
    if dimensions is None:
        warnings.append("Não foi possível extrair dimensões da imagem APP.")
        return

    width, height = dimensions
    details["image_width"] = width
    details["image_height"] = height

    if commercial_space:
        details["commercial_space"] = commercial_space

    # Validação com espaço comercial específico (expected_width/expected_height)
    expected_w = image_specs.get("expected_width")
    expected_h = image_specs.get("expected_height")

    if expected_w and expected_h:
        tolerance_pct = image_specs.get("tolerance_pct", 5) / 100

        details["expected_width"] = expected_w
        details["expected_height"] = expected_h
        details["tolerance_pct"] = image_specs.get("tolerance_pct", 5)

        w_min = int(expected_w * (1 - tolerance_pct))
        w_max = int(expected_w * (1 + tolerance_pct))
        h_min = int(expected_h * (1 - tolerance_pct))
        h_max = int(expected_h * (1 + tolerance_pct))

        if not (w_min <= width <= w_max):
            errors.append(
                f"Largura da imagem ({width}px) fora do esperado para "
                f"'{commercial_space}' ({expected_w}px ±{image_specs.get('tolerance_pct', 5)}%)."
            )
        if not (h_min <= height <= h_max):
            errors.append(
                f"Altura da imagem ({height}px) fora do esperado para "
                f"'{commercial_space}' ({expected_h}px ±{image_specs.get('tolerance_pct', 5)}%)."
            )
    else:
        # Validação genérica (limites min/max globais)
        min_w = generic_specs.get("min_width", 300)
        min_h = generic_specs.get("min_height", 300)
        max_w = generic_specs.get("max_width", 4096)
        max_h = generic_specs.get("max_height", 4096)

        details["min_width"] = min_w
        details["min_height"] = min_h
        details["max_width"] = max_w
        details["max_height"] = max_h

        if width < min_w or height < min_h:
            errors.append(
                f"Imagem muito pequena ({width}x{height}px). "
                f"Mínimo: {min_w}x{min_h}px."
            )
        if width > max_w or height > max_h:
            errors.append(
                f"Imagem muito grande ({width}x{height}px). "
                f"Máximo: {max_w}x{max_h}px."
            )

        # Aviso se não tem espaço comercial definido
        if not commercial_space:
            warnings.append(
                "Espaço comercial não informado — validação genérica de dimensões aplicada. "
                "Informe o espaço comercial para validação mais precisa."
            )


# ---------------------------------------------------------------------------
# Helpers de imagem
# ---------------------------------------------------------------------------

def _decode_image_bytes(data_url: str) -> bytes | None:
    """Decodifica data URL base64 para bytes."""
    try:
        idx = data_url.find(";base64,")
        if idx == -1:
            return None
        payload = data_url[idx + 8:]
        return base64.b64decode(payload)
    except Exception:
        return None


def _get_image_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    """Extrai dimensões (width, height) de bytes de imagem usando Pillow."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        return img.size  # (width, height)
    except ImportError:
        logger.warning("Pillow not installed — skipping image dimension validation")
        return None
    except Exception as e:
        logger.warning("Failed to get image dimensions: %s", e)
        return None


# ===========================================================================
# Self-test
# ===========================================================================

if __name__ == "__main__":
    # Nível 1 — estrutura
    r = validate_piece_format_and_size("SMS", {"body": "Olá, teste."})
    assert r["valid"] and "OK" in r["message"], r
    r = validate_piece_format_and_size("SMS", {})
    assert not r["valid"] and "body" in r["errors"][0], r
    r = validate_piece_format_and_size("APP", {"image": "not-a-data-url"})
    assert not r["valid"] and "data URL" in r["errors"][0], r

    # Nível 2 — specs
    r = validate_piece_specs("SMS", {"body": "x" * 200})
    assert not r["valid"]  # 200 chars > 160 = error
    r = validate_piece_specs("SMS", {"body": "x" * 100})
    assert r["valid"]  # 100 chars OK
    r = validate_piece_specs("SMS", {"body": ""})
    assert not r["valid"]  # vazio = error
    r = validate_piece_specs("PUSH", {"title": "x" * 80, "body": "ok"})
    assert not r["valid"]  # Title > 50
    r = validate_piece_specs("PUSH", {"title": "ok", "body": "ok"})
    assert r["valid"]

    print("validate_piece OK — all tests passed")
