from unittest.mock import patch

# ── Validação de estrutura ────────────────────────────────────────────────

def test_sms_valid_structure():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("SMS", {"body": "Olá, cliente!"})
    assert result["valid"] is True


def test_sms_missing_body():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("SMS", {})
    assert result["valid"] is False
    assert any("body" in e for e in result["errors"])


def test_push_valid_structure():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("PUSH", {"title": "Oferta", "body": "Confira"})
    assert result["valid"] is True


def test_push_missing_title():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("PUSH", {"body": "Corpo"})
    assert result["valid"] is False


def test_email_valid_structure():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("EMAIL", {"html": "<html><body>Oi</body></html>"})
    assert result["valid"] is True


def test_email_missing_html():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("EMAIL", {"body": "texto"})
    assert result["valid"] is False


def test_invalid_channel():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("WHATSAPP", {"body": "oi"})
    assert result["valid"] is False
    assert "Canal inválido" in result["message"]


def test_content_not_dict():
    from app.core.validators import validate_piece_format_and_size
    result = validate_piece_format_and_size("SMS", "texto simples")
    assert result["valid"] is False


# ── Validação de specs (char limits) ──────────────────────────────────────

def test_sms_specs_within_limit():
    from app.core.validators import validate_piece_specs
    specs = {"body": {"min_chars": 1, "max_chars": 160}}
    result = validate_piece_specs("SMS", {"body": "Mensagem curta"}, remote_specs={"specs": specs})
    assert result["valid"] is True


def test_sms_specs_exceeds_limit():
    from app.core.validators import validate_piece_specs
    specs = {"body": {"min_chars": 1, "max_chars": 160}}
    result = validate_piece_specs("SMS", {"body": "A" * 200}, remote_specs={"specs": specs})
    assert result["valid"] is False
    assert any("160" in e for e in result["errors"])


def test_sms_specs_empty_body():
    from app.core.validators import validate_piece_specs
    specs = {"body": {"min_chars": 1, "max_chars": 160}}
    result = validate_piece_specs("SMS", {"body": ""}, remote_specs={"specs": specs})
    assert result["valid"] is False


def test_push_specs_title_too_long():
    from app.core.validators import validate_piece_specs
    specs = {"title": {"max_chars": 50}, "body": {"max_chars": 150}}
    result = validate_piece_specs("PUSH", {"title": "A" * 80, "body": "ok"}, remote_specs={"specs": specs})
    assert result["valid"] is False


# ── Construção do veredito ────────────────────────────────────────────────

def test_build_verdict_approved():
    from app.agent.nodes import _build_verdict
    result = _build_verdict(
        decision="approved",
        summary="Tudo em conformidade.",
        requires_human=False,
        human_reason=None,
        failure_stage=None,
        stages_completed=["format", "specs", "branding", "compliance", "verdict"],
        specs_result={"valid": True},
        branding_result={"compliant": True},
        compliance_result={"decision": "APROVADO", "summary": "OK"},
        sources=["doc1.pdf"],
    )
    verdict = result["final_verdict"]
    assert verdict["decision"] == "approved"
    assert verdict["requires_human_review"] is False
    assert verdict["failure_stage"] is None
    assert "doc1.pdf" in verdict["sources"]
    assert verdict["legal"]["decision"] == "APROVADO"


def test_build_verdict_rejected_at_specs():
    from app.agent.nodes import _build_verdict
    result = _build_verdict(
        decision="rejected",
        summary="SMS excede 160 caracteres.",
        requires_human=False,
        failure_stage="specs",
        stages_completed=["format", "specs"],
        specs_result={"valid": False, "errors": ["Excede 160 chars"]},
    )
    verdict = result["final_verdict"]
    assert verdict["decision"] == "rejected"
    assert verdict["failure_stage"] == "specs"
    assert len(verdict["stages_completed"]) == 2


def test_build_verdict_with_compliance_error():
    from app.agent.nodes import _build_verdict
    result = _build_verdict(
        decision="rejected",
        summary="Erro na validação legal.",
        requires_human=True,
        human_reason="Falha ao consultar serviço jurídico",
        failure_stage="compliance",
        stages_completed=["format", "specs", "branding"],
        compliance_error="Connection timeout",
    )
    orch = result["orchestration_result"]
    assert orch["compliance"] == {"error": "Connection timeout"}
    assert result["requires_human_approval"] is True
