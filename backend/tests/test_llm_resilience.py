"""Tests for LLM cooldown circuit breaker and malformed payload resilience."""

from types import SimpleNamespace
import pytest

from app.services import llm_client


def test_llm_circuit_breaker_short_circuits_after_quota_error(monkeypatch: pytest.MonkeyPatch):
    llm_client.clear_llm_cooldowns()
    calls = 0

    class FailingChatModel:
        def __init__(self, **_kwargs):
            pass

        def invoke(self, _messages):
            nonlocal calls
            calls += 1
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")

    fake_settings = SimpleNamespace(
        effective_llm_provider="gemini",
        llm_timeout_seconds=10,
        gemini_api_key="dummy-key-for-circuit-breaker-test",
        gemini_model="gemini-2.5-flash",
    )
    monkeypatch.setattr(llm_client, "get_settings", lambda: fake_settings)
    monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI", FailingChatModel)

    first = llm_client.invoke_llm_json("sys", "usr")
    second = llm_client.invoke_llm_json("sys", "usr")
    assert first.used_llm is False
    assert second.used_llm is False
    assert calls == 1  # second invocation skips API call cleanly due to cooldown

    llm_client.clear_llm_cooldowns()
    third = llm_client.invoke_llm_json("sys", "usr")
    assert third.used_llm is False
    assert calls == 2
    llm_client.clear_llm_cooldowns()


def test_extract_message_text_handles_multimodal_block_lists():
    blocks = [
        {"type": "text", "text": '```json\n{"topics": [{"title": "OS"}]}\n```'},
    ]
    extracted = llm_client._extract_message_text(blocks)
    parsed = llm_client._extract_json_payload(extracted)
    assert isinstance(parsed, dict)
    assert parsed["topics"][0]["title"] == "OS"


def test_groq_provider_priority_and_openai_compatible_client(monkeypatch: pytest.MonkeyPatch):
    from app.config import Settings

    s_auto = Settings(llm_provider="auto", groq_api_key="gsk_dummy", gemini_api_key="gem_dummy")
    assert s_auto.effective_llm_provider == "groq"

    s_explicit = Settings(llm_provider="groq", groq_api_key="gsk_dummy")
    assert s_explicit.effective_llm_provider == "groq"

    captured: dict = {}

    class DummyGroqChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    llm_client.clear_llm_cooldowns()
    monkeypatch.setattr(llm_client, "get_settings", lambda: s_explicit)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", DummyGroqChat)

    model, cache_key = llm_client._build_chat_model(temperature=0.1)
    assert model is not None
    assert cache_key is not None and cache_key[0] == "groq"
    assert captured["base_url"] == "https://api.groq.com/openai/v1"
    assert captured["model"] == "openai/gpt-oss-120b"
    assert captured["max_retries"] == 0


def test_extract_json_payload_handles_inner_markdown_code_fences():
    raw = (
        '```json\n'
        '{\n'
        '  "explanation": "7 layers:\\n\\n```\\n[Application]\\n[Physical]\\n```\\nDone.",\n'
        '  "analogy": "Postal stack",\n'
        '  "flashcards": [{"front": "How many?", "back": "7"}]\n'
        '}\n'
        '```'
    )
    parsed = llm_client._extract_json_payload(raw)
    assert isinstance(parsed, dict)
    assert "7 layers" in parsed["explanation"]
    assert parsed["flashcards"][0]["back"] == "7"
