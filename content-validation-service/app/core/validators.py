from __future__ import annotations
import base64
import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional
import yaml

logger = logging.getLogger(__name__)

_SPECS_PATH = os.environ.get(
    "CHANNEL_SPECS_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "config" / "channel_specs.yaml"),
)

_channel_specs: dict[str, Any] | None = None


def _load_specs() -> dict[str, Any]:
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
    specs = _load_specs()
    return specs.get(channel.upper(), {})


_DATA_URL_PATTERN = re.compile(
    r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=]+$"
)


def validate_piece_format_and_size(
    channel: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    details: dict[str, Any] = {"channel": channel}

    if channel not in ("SMS", "PUSH", "EMAIL", "APP"):
        return {
            "valid": False,
            "message": f"Canal inválido: {channel}. Use SMS, PUSH, EMAIL ou APP.",
            "errors": [f"Canal inválido: {channel}"],
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
    if "body" not in content:
        errors.append("Para channel=SMS, content deve ter 'body'.")
        return
    if not isinstance(content["body"], str):
        errors.append("content.body deve ser string.")


def _validate_push_structure(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    for key in ("title", "body"):
        if key not in content:
            errors.append(f"Para channel=PUSH, content deve ter '{key}'.")
            continue
        if not isinstance(content[key], str):
            errors.append(f"content.{key} deve ser string.")


def _validate_email_structure(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
    if "html" not in content:
        errors.append("Para channel=EMAIL, content deve ter 'html'.")
        return
    if not isinstance(content["html"], str):
        errors.append("content.html deve ser string.")


def _validate_app_structure(content: dict[str, Any], errors: list[str], details: dict[str, Any]) -> None:
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


def validate_piece_specs(
    channel: str,
    content: dict[str, Any],
    commercial_space: Optional[str] = None,
    conversion_metadata: Optional[dict[str, Any]] = None,
    remote_specs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {"channel": channel, "specs_source": "remote" if remote_specs else "local"}

    if remote_specs and remote_specs.get("specs"):
        specs_by_field = remote_specs["specs"]
        generic_by_field = remote_specs.get("generic_specs", {})
    else:
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
        _validate_app_specs(content, specs_by_field, generic_by_field, commercial_space, errors, warnings, details)

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

        if commercial_space:
            space_key = commercial_space.strip().lower().replace(" ", "_")
            space_map = local_specs.get("commercial_spaces", {})
            space_data = space_map.get(space_key, {})
            if space_data:
                result["image"] = {**result.get("image", {}), **space_data}

    return result


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


def _validate_app_specs(
    content: dict[str, Any],
    specs_by_field: dict[str, dict[str, Any]],
    generic_by_field: dict[str, dict[str, Any]],
    commercial_space: Optional[str],
    errors: list[str],
    warnings: list[str],
    details: dict[str, Any],
) -> None:
    image_data = content.get("image", "")
    if not isinstance(image_data, str) or not image_data:
        return

    image_specs = specs_by_field.get("image", {})
    generic_specs = generic_by_field.get("image", {})

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

    dimensions = _get_image_dimensions(image_bytes)
    if dimensions is None:
        warnings.append("Não foi possível extrair dimensões da imagem APP.")
        return

    width, height = dimensions
    details["image_width"] = width
    details["image_height"] = height

    if commercial_space:
        details["commercial_space"] = commercial_space

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

        if not commercial_space:
            warnings.append(
                "Espaço comercial não informado — validação genérica de dimensões aplicada. "
                "Informe o espaço comercial para validação mais precisa."
            )


def _decode_image_bytes(data_url: str) -> bytes | None:
    try:
        idx = data_url.find(";base64,")
        if idx == -1:
            return None
        payload = data_url[idx + 8:]
        return base64.b64decode(payload)
    except Exception:
        return None


def _get_image_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        return img.size
    except ImportError:
        logger.warning("Pillow not installed — skipping image dimension validation")
        return None
    except Exception as e:
        logger.warning("Failed to get image dimensions: %s", e)
        return None
