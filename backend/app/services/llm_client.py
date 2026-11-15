"""Modular LLM adapter with structured JSON parsing and safe offline fallback."""

from dataclasses import dataclass
import json
import re
from typing import Any

from app.config import get_settings


@dataclass
class LLMResponse:
    """Result container clearly reporting whether live LLM or fallback ran."""

    content: str
    parsed: Any | None
    used_llm: bool
    execution_mode: str
    error: str | None = None


def _extract_json_payload(raw_text: str) -> Any | None:
    """Extract and parse a JSON object or array from an LLM text response."""
    cleaned = raw_text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            start = cleaned.find(open_ch)
            end = cleaned.rfind(close_ch)
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    continue
    return None


def _build_chat_model(temperature: float = 0.2):
    """Instantiate Gemini or OpenAI chat model when configured cleanly."""
    settings = get_settings()
    provider = settings.effective_llm_provider
    timeout = settings.llm_timeout_seconds

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
            timeout=timeout,
            max_retries=1,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            timeout=timeout,
            max_retries=1,
        )
    return None


def invoke_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> LLMResponse:
    """Invoke configured LLM expecting JSON; return fallback metadata cleanly on failure."""
    model = None
    try:
        model = _build_chat_model(temperature=temperature)
    except Exception as exc:  # noqa: BLE001
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error=str(exc),
        )

    if model is None:
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error="No live LLM API key configured; running offline fallback.",
        )

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        msg = model.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        raw_text = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
        parsed = _extract_json_payload(raw_text)
        if parsed is None:
            return LLMResponse(
                content=raw_text,
                parsed=None,
                used_llm=False,
                execution_mode="fallback",
                error="LLM response did not contain valid JSON; triggered fallback.",
            )
        return LLMResponse(
            content=raw_text,
            parsed=parsed,
            used_llm=True,
            execution_mode="llm",
        )
    except Exception as exc:  # noqa: BLE001
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error=str(exc),
        )


def invoke_llm_text(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.35,
) -> LLMResponse:
    """Invoke configured LLM expecting prose output; degrade gracefully on error."""
    try:
        model = _build_chat_model(temperature=temperature)
    except Exception as exc:  # noqa: BLE001
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error=str(exc),
        )
    if model is None:
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error="No live LLM API key configured.",
        )
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        msg = model.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        raw_text = msg.content if isinstance(msg.content, str) else str(msg.content)
        return LLMResponse(
            content=raw_text.strip(),
            parsed=None,
            used_llm=bool(raw_text.strip()),
            execution_mode="llm" if raw_text.strip() else "fallback",
        )
    except Exception as exc:  # noqa: BLE001
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error=str(exc),
        )
