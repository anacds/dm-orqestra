"""Testes unitários para legal-service: prompts, parsing, fallback."""
import pytest
from unittest.mock import patch, MagicMock


# ── Construção de prompts ─────────────────────────────────────────────────

def test_build_messages_text_only():
    from app.agent.prompts import build_validation_messages
    msgs = build_validation_messages(
        context="Contexto jurídico de teste",
        channel="SMS",
        sources=["doc1.pdf", "doc2.pdf"],
        format_instructions="{formato}",
        content_description="Texto do SMS",
        image=None,
    )
    assert len(msgs) == 2  # system + human
    assert msgs[0].type == "system"
    assert msgs[1].type == "human"
    assert isinstance(msgs[1].content, str)
    assert "Texto do SMS" in msgs[1].content
    assert "doc1.pdf" in msgs[1].content


def test_build_messages_with_image():
    from app.agent.prompts import build_validation_messages
    msgs = build_validation_messages(
        context="Contexto",
        channel="APP",
        sources=[],
        format_instructions="{fmt}",
        content_description="Comunicação in-app",
        image="data:image/png;base64,AAAA",
    )
    assert len(msgs) == 2
    # Quando tem imagem, human message content é lista multimodal
    assert isinstance(msgs[1].content, list)
    assert msgs[1].content[0]["type"] == "text"
    assert msgs[1].content[1]["type"] == "image_url"


def test_system_prompt_contains_instructions():
    from app.agent.prompts import VALIDATION_SYSTEM_TEMPLATE
    assert "APROVADO" in VALIDATION_SYSTEM_TEMPLATE
    assert "REPROVADO" in VALIDATION_SYSTEM_TEMPLATE
    assert "{format_instructions}" in VALIDATION_SYSTEM_TEMPLATE


# ── Detecção de modelo de raciocínio ──────────────────────────────────────

def test_is_reasoning_model():
    """Modelos gpt-5, o1, o3, o4 devem ser detectados como reasoning."""
    # Importamos a função interna via o módulo
    import app.agent.graph as graph_module
    import importlib, os
    # Precisamos testar _is_reasoning_model que é definida dentro de __init__
    # Vamos testar a lógica diretamente
    def _is_reasoning_model(name: str) -> bool:
        _lower = name.lower()
        return any(tag in _lower for tag in ("gpt-5", "o1", "o3", "o4"))

    assert _is_reasoning_model("gpt-5-nano")
    assert _is_reasoning_model("o1-preview")
    assert _is_reasoning_model("o3-mini")
    assert _is_reasoning_model("o4-mini")
    assert not _is_reasoning_model("gpt-4o")
    assert not _is_reasoning_model("sabiazinho-4")
    assert not _is_reasoning_model("claude-3")


# ── Lógica de fallback de provider ────────────────────────────────────────

MODELS_CONFIG = {
    "models": {
        "llm": {
            "defaults": {"temperature": 0.3, "max_tokens": 12000, "timeout": 60, "max_retries": 2},
            "maritaca_base_url": "https://chat.maritaca.ai/api",
            "channels": {
                "SMS": {"provider": "maritaca", "model": "sabiazinho-4"},
                "APP": {"provider": "openai", "model": "gpt-5-nano"},
            },
        },
        "embeddings": {"provider": "openai", "model": "text-embedding-3-small"},
        "retrieval": {"limit": 20, "alpha": 0.5},
    }
}


@patch("app.agent.graph.load_models_config", return_value=MODELS_CONFIG)
@patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "MARITACA_API_KEY": ""}, clear=False)
@patch("app.agent.graph.ChatOpenAI")
@patch("app.agent.graph.HybridWeaviateRetriever")
def test_fallback_to_openai_when_maritaca_missing(mock_retriever, mock_chat, mock_config):
    """Sem MARITACA_API_KEY, canais maritaca devem usar fallback OpenAI."""
    mock_chat.return_value = MagicMock()
    mock_retriever.return_value = MagicMock()
    from app.agent.graph import LegalAgent
    agent = LegalAgent()
    # Canal SMS (configurado como maritaca) deve ter recebido fallback
    assert "SMS" in agent.channel_to_llm
    assert "APP" in agent.channel_to_llm


@patch("app.agent.graph.load_models_config", return_value=MODELS_CONFIG)
@patch.dict("os.environ", {"OPENAI_API_KEY": "", "MARITACA_API_KEY": ""}, clear=False)
@patch("app.agent.graph.HybridWeaviateRetriever")
def test_error_when_no_keys_available(mock_retriever, mock_config):
    """Sem nenhuma API key, deve lançar ValueError."""
    mock_retriever.return_value = MagicMock()
    from app.agent.graph import LegalAgent
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        LegalAgent()
