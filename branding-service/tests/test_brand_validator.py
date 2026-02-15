import base64
import io
from PIL import Image


# ── Helpers de cor ────────────────────────────────────────────────────────

def test_normalize_hex_shorthand():
    from app.services.image_color_validator import _normalize_hex
    assert _normalize_hex("#fff") == "#ffffff"
    assert _normalize_hex("6b7fff") == "#6b7fff"
    assert _normalize_hex("#6B7FFF") == "#6b7fff"


def test_rgb_to_hex():
    from app.services.image_color_validator import _rgb_to_hex
    assert _rgb_to_hex(255, 255, 255) == "#ffffff"
    assert _rgb_to_hex(0, 0, 0) == "#000000"
    assert _rgb_to_hex(107, 127, 255) == "#6b7fff"


def test_color_distance_identical():
    from app.services.image_color_validator import _color_distance
    assert _color_distance("#6b7fff", "#6b7fff") == 0


def test_color_distance_black_white():
    from app.services.image_color_validator import _color_distance
    assert _color_distance("#000000", "#ffffff") == 255 * 3


def test_color_in_palette_exact_match():
    from app.services.image_color_validator import _color_in_palette
    assert _color_in_palette("#6b7fff")  # cor primária
    assert _color_in_palette("#ffffff")  # branco


def test_color_in_palette_within_tolerance():
    from app.services.image_color_validator import _color_in_palette
    # Cor muito próxima da primária #6b7fff
    assert _color_in_palette("#6a7efe")


def test_color_not_in_palette():
    from app.services.image_color_validator import _color_in_palette
    assert not _color_in_palette("#ff0000")  # vermelho puro


# ── Validação de imagem (threshold 50%) ───────────────────────────────────

def _make_solid_image_base64(color: tuple, size=(100, 100)) -> str:
    """Cria uma imagem sólida e retorna como data URL base64."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def test_approved_color_image_is_compliant():
    from app.services.image_color_validator import validate_image_branding
    # Imagem toda na cor primária
    result = validate_image_branding(_make_solid_image_base64((107, 127, 255)))
    assert result["compliant"] is True
    critical = [v for v in result["violations"] if v["severity"] == "critical"]
    assert len(critical) == 0


def test_unapproved_color_above_50_is_critical():
    from app.services.image_color_validator import validate_image_branding
    # Imagem toda vermelha (100% fora da paleta)
    result = validate_image_branding(_make_solid_image_base64((255, 0, 0)))
    critical = [v for v in result["violations"] if v["severity"] == "critical"]
    assert len(critical) >= 1
    assert critical[0]["rule"] == "unapproved_color_ratio"


def test_invalid_base64_returns_error():
    from app.services.image_color_validator import validate_image_branding
    result = validate_image_branding("data:image/png;base64,INVALIDO!!!")
    assert result["compliant"] is False
    assert result["violations"][0]["rule"] == "invalid_image"


# ── BrandValidator: parsing HTML e fontes ─────────────────────────────────

def test_extract_colors_from_html():
    from app.services.brand_validator import BrandValidator
    v = BrandValidator()
    colors = v._extract_colors("color: #6b7fff; background: rgb(255, 0, 0);")
    assert "#6b7fff" in colors
    assert "#ff0000" in colors


def test_approved_font_passes():
    from app.services.brand_validator import BrandValidator
    v = BrandValidator()
    v.violations = []
    v._validate_fonts("font-family: Arial, Helvetica, sans-serif;")
    font_violations = [v for v in v.violations if v.category == "typography" and "não aprovada" in v.message]
    assert len(font_violations) == 0


def test_unapproved_font_fails():
    from app.services.brand_validator import BrandValidator
    v = BrandValidator()
    v.violations = []
    v._validate_fonts("font-family: 'Comic Sans MS';")
    font_violations = [v for v in v.violations if v.category == "typography" and "não aprovada" in v.message]
    assert len(font_violations) >= 1


def test_font_size_too_small():
    from app.services.brand_validator import BrandValidator
    v = BrandValidator()
    v.violations = []
    v._validate_fonts("font-size: 8px;")
    size_violations = [v for v in v.violations if v.rule == "font_size_too_small"]
    assert len(size_violations) == 1
    assert "8px" in size_violations[0].value


def test_normalize_rgb_to_hex():
    from app.services.brand_validator import BrandValidator
    v = BrandValidator()
    assert v._normalize_color("rgb(107, 127, 255)") == "#6b7fff"
    assert v._normalize_color("#FFF") == "#ffffff"
