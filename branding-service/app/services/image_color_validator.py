import base64
import io
import re
from collections import Counter
from typing import Dict, Any, List, Set
from PIL import Image
from app.services.brand_validator import BrandValidator

APPROVED_COLORS: Set[str] = BrandValidator.APPROVED_COLORS
PRIMARY_COLORS: Set[str] = BrandValidator.PRIMARY_COLORS

# Tolerância para considerar cores "próximas" 
_COLOR_TOLERANCE = 25  # delta RGB máximo para considerar equivalente
_DOMINANT_COUNT = 8  # número de cores dominantes a analisar
_SAMPLE_SIZE = (80, 80)  # redimensionar para extração rápida


def _extract_base64_payload(image_input: str) -> bytes:
    """Extrai payload base64 de data URL ou string base64 pura."""
    image_input = image_input.strip()
    if image_input.startswith("data:"):
        # data:image/png;base64,XXXX
        match = re.search(r"base64\s*,\s*([A-Za-z0-9+/=]+)", image_input)
        if not match:
            raise ValueError("Data URL inválida: base64 não encontrado")
        payload = match.group(1)
    else:
        payload = image_input
    return base64.b64decode(payload)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Converte RGB para hex."""
    return f"#{r:02x}{g:02x}{b:02x}".lower()


def _normalize_hex(hex_color: str) -> str:
    """Normaliza hex para formato #rrggbb."""
    h = hex_color.strip().lower()
    if not h.startswith("#"):
        h = "#" + h
    if len(h) == 4:  # #fff -> #ffffff
        h = "#" + "".join(c * 2 for c in h[1:])
    return h


def _hex_to_rgb(hex_color: str) -> tuple:
    """Converte hex para (r, g, b)."""
    h = _normalize_hex(hex_color).lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _color_distance(c1: str, c2: str) -> int:
    """Distância RGB entre duas cores (0 = idênticas)."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)


def _color_in_palette(hex_color: str, tolerance: int = 40) -> bool:
    """Verifica se a cor está na paleta aprovada (com tolerância para compressão)."""
    h = _normalize_hex(hex_color)
    if h in APPROVED_COLORS:
        return True
    # Tolerância: cor próxima de alguma aprovada
    for approved in APPROVED_COLORS:
        if _color_distance(h, approved) <= tolerance:
            return True
    return False


def _is_primary_color(hex_color: str, tolerance: int = 50) -> bool:
    """Verifica se a cor é considerada primária (azul Orqestra)."""
    h = _normalize_hex(hex_color)
    for primary in PRIMARY_COLORS:
        if _color_distance(h, primary) <= tolerance:
            return True
    return False


def _extract_dominant_colors(image: Image.Image) -> List[tuple]:
    """
    Extrai as cores dominantes da imagem.
    Retorna lista de (hex_color, count) ordenada por frequência.
    """
    img = image.convert("RGB")
    img = img.resize(_SAMPLE_SIZE, Image.Resampling.LANCZOS)
    pixels = list(img.getdata())

    # Agrupa cores similares (quantização leve) para evitar ruído
    def quantize(r: int, g: int, b: int, step: int = 16) -> tuple:
        return (
            (r // step) * step,
            (g // step) * step,
            (b // step) * step,
        )

    quantized = [quantize(r, g, b) for r, g, b in pixels]
    counts = Counter(quantized)

    # Ordena por frequência e converte para hex
    result = []
    for (r, g, b), count in counts.most_common(_DOMINANT_COUNT):
        # Usa o centro do bucket para o hex final (step 16 -> +8)
        r = min(255, r + 8)
        g = min(255, g + 8)
        b = min(255, b + 8)
        hex_color = _rgb_to_hex(r, g, b)
        result.append((hex_color, count))
    return result


def validate_image_branding(image: str) -> Dict[str, Any]:
    """
    Valida as cores dominantes de uma imagem contra a paleta Orqestra.

    Args:
        image: Imagem em base64 ou data URL (data:image/png;base64,...)

    Returns:
        Dict com compliant, score, violations, summary, dominant_colors
    """
    violations = []
    dominant_colors: List[Dict[str, Any]] = []

    try:
        payload = _extract_base64_payload(image)
        img = Image.open(io.BytesIO(payload))
        img = img.convert("RGB")
    except Exception as e:
        return {
            "compliant": False,
            "score": 0,
            "violations": [
                {
                    "rule": "invalid_image",
                    "category": "image",
                    "severity": "critical",
                    "value": "",
                    "message": f"Imagem inválida ou corrompida: {e}",
                }
            ],
            "summary": {"critical": 1, "warning": 0, "info": 0, "total": 1},
            "dominant_colors": [],
        }

    colors_with_counts = _extract_dominant_colors(img)
    has_primary = False

    for hex_color, count in colors_with_counts:
        dominant_colors.append({"color": hex_color, "count": count})
        normalized = _normalize_hex(hex_color)

        if _is_primary_color(normalized):
            has_primary = True

        # Ignora branco/cinza muito claro e preto (background comum)
        if normalized in ("#ffffff", "#fff", "#fefefe", "#f5f5f5", "#f8f9ff"):
            continue
        if normalized in ("#000000", "#000", "#0a0a0a", "#1a1a1a"):
            continue

        if not _color_in_palette(normalized):
            violations.append(
                {
                    "rule": "unapproved_color",
                    "category": "colors",
                    "severity": "critical",
                    "value": hex_color,
                    "message": f"Cor {hex_color} não está na paleta aprovada da marca",
                }
            )

    if not has_primary and dominant_colors:
        # Só avisa se há cores significativas e nenhuma é primária
        violations.append(
            {
                "rule": "missing_primary_color",
                "category": "colors",
                "severity": "warning",
                "value": "",
                "message": "Cor primária da marca (#6B7FFF) não detectada nas cores principais",
            }
        )

    critical = sum(1 for v in violations if v["severity"] == "critical")
    warning = sum(1 for v in violations if v["severity"] == "warning")
    info = sum(1 for v in violations if v["severity"] == "info")

    score = 100 - critical * 20 - warning * 5 - info * 1
    score = max(0, score)
    compliant = critical == 0 and warning == 0

    return {
        "compliant": compliant,
        "score": score,
        "violations": violations,
        "summary": {
            "critical": critical,
            "warning": warning,
            "info": info,
            "total": len(violations),
        },
        "dominant_colors": dominant_colors,
    }
