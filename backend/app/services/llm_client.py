"""Modular LLM adapter with structured JSON parsing, cooldown circuit breaker, and safe fallback."""

from dataclasses import dataclass
import hashlib
import json
import re
import time
from typing import Any

from app.config import get_settings

# In-memory circuit breaker: maps (provider, key_fingerprint) -> unix timestamp when retry is allowed.
_PROVIDER_COOLDOWN_UNTIL: dict[tuple[str, str], float] = {}


def clear_llm_cooldowns() -> None:
    """Reset cached LLM provider cooldown state (primarily for tests)."""
    _PROVIDER_COOLDOWN_UNTIL.clear()


def _provider_cache_key(provider: str, secret: str) -> tuple[str, str]:
    fingerprint = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]
    return (provider, fingerprint)


def _cooldown_reason(exc: Exception) -> int:
    """Return cooldown duration in seconds based on quota/auth/model vs transient failure."""
    msg = str(exc).lower()
    if "length limit" in msg or "finish_reason" in msg:
        return 0
    terminal_tokens = (
        "429",
        "resource_exhausted",
        "quota",
        "401",
        "403",
        "404",
        "model_not_found",
        "does not exist",
        "api_key_invalid",
        "invalid api key",
        "permission_denied",
        "billing",
    )
    if any(tok in msg for tok in terminal_tokens):
        return 120
    return 30


def _extract_message_text(content: Any) -> str:
    """Normalize LangChain AIMessage.content (str or multimodal block list) to plain text."""
    if isinstance(content, str):
        raw = content
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if "text" in block:
                    parts.append(str(block["text"]))
                elif "content" in block:
                    parts.append(str(block["content"]))
        raw = "\n".join(parts) if parts else json.dumps(content, default=str)
    else:
        raw = json.dumps(content, default=str)
    return re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE).strip()


@dataclass
class LLMResponse:
    """Result container clearly reporting whether live LLM or fallback ran."""

    content: str
    parsed: Any | None
    used_llm: bool
    execution_mode: str
    error: str | None = None


def _extract_json_payload(raw_text: str) -> Any | None:
    """Extract and parse a JSON object or array cleanly even if string values hold inner code fences."""
    text = raw_text.strip()
    candidates: list[str] = [text]

    greedy_fence = re.search(r"```(?:json)?\s*([\s\S]*)```", text, flags=re.IGNORECASE)
    if greedy_fence:
        candidates.append(greedy_fence.group(1).strip())

    lazy_fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if lazy_fence:
        candidates.append(lazy_fence.group(1).strip())

    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            for open_ch, close_ch in (("{", "}"), ("[", "]")):
                start = cand.find(open_ch)
                end = cand.rfind(close_ch)
                if start != -1 and end > start:
                    try:
                        return json.loads(cand[start : end + 1])
                    except json.JSONDecodeError:
                        continue
    return None


def _build_openai_compatible(
    provider: str,
    model_name: str,
    api_key: str,
    temperature: float,
    timeout: int,
    base_url: str | None = None,
):
    """Instantiate an OpenAI or Groq (OpenAI-compatible) chat client respecting cooldown."""
    cache_key = _provider_cache_key(provider, api_key)
    if time.monotonic() < _PROVIDER_COOLDOWN_UNTIL.get(cache_key, 0.0):
        return None, cache_key
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": 0,
    }
    if base_url:
        kwargs["base_url"] = base_url
    if provider == "groq":
        kwargs["max_tokens"] = 4096
        kwargs["extra_body"] = {"reasoning_effort": "low"}
    return ChatOpenAI(**kwargs), cache_key


def _build_chat_model(temperature: float = 0.2):
    """Instantiate Groq, Gemini, or OpenAI chat model when configured and not in cooldown."""
    settings = get_settings()
    provider = settings.effective_llm_provider
    timeout = settings.llm_timeout_seconds

    if provider == "groq":
        return _build_openai_compatible(
            provider="groq",
            model_name=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temperature,
            timeout=timeout,
            base_url="https://api.groq.com/openai/v1",
        )
    if provider == "gemini":
        cache_key = _provider_cache_key(provider, settings.gemini_api_key)
        if time.monotonic() < _PROVIDER_COOLDOWN_UNTIL.get(cache_key, 0.0):
            return None, cache_key
        from langchain_google_genai import ChatGoogleGenerativeAI

        return (
            ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=temperature,
                timeout=timeout,
                max_retries=0,
            ),
            cache_key,
        )
    if provider == "openai":
        return _build_openai_compatible(
            provider="openai",
            model_name=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            timeout=timeout,
        )
    return None, None


def _invoke_raw(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    json_mode: bool = False,
) -> tuple[str | None, str | None]:
    """Invoke active chat model with circuit-breaker recording on errors."""
    try:
        model, cache_key = _build_chat_model(temperature=temperature)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)

    if model is None:
        if cache_key is not None:
            return None, "LLM provider temporarily paused due to recent quota/API failure; using fallback."
        return None, "No live LLM API key configured; running offline fallback."

    if (
        json_mode
        and cache_key is not None
        and cache_key[0] in {"groq", "openai"}
        and "json" in f"{system_prompt} {user_prompt}".lower()
        and hasattr(model, "bind")
    ):
        model = model.bind(response_format={"type": "json_object"})

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        msg = model.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        return _extract_message_text(msg.content), None
    except Exception as exc:  # noqa: BLE001
        if cache_key is not None:
            _PROVIDER_COOLDOWN_UNTIL[cache_key] = time.monotonic() + _cooldown_reason(exc)
        return None, str(exc)


def invoke_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> LLMResponse:
    """Invoke configured LLM expecting JSON; return fallback metadata cleanly on failure."""
    raw_text, err = _invoke_raw(system_prompt, user_prompt, temperature=temperature, json_mode=True)
    if raw_text is None:
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error=err,
        )

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


def invoke_llm_text(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.35,
) -> LLMResponse:
    """Invoke configured LLM expecting prose output; degrade gracefully on error."""
    raw_text, err = _invoke_raw(system_prompt, user_prompt, temperature=temperature)
    if raw_text is None:
        return LLMResponse(
            content="",
            parsed=None,
            used_llm=False,
            execution_mode="fallback",
            error=err,
        )
    cleaned = raw_text.strip()
    return LLMResponse(
        content=cleaned,
        parsed=None,
        used_llm=bool(cleaned),
        execution_mode="llm" if cleaned else "fallback",
    )
