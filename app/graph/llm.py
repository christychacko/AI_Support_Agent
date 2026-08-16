"""
Primary/fallback model wrapper.

Provider is configurable per-slot via env vars (PRIMARY_PROVIDER /
FALLBACK_PROVIDER, each "groq" or "ollama"), so you can run:

  - Groq primary + Groq fallback (fastest to start, needs one free API key)
  - Groq primary + Ollama fallback (free cloud speed, free local safety net --
    useful when you hit Groq's rate limit)
  - Ollama primary + Ollama fallback (fully offline, zero API keys, zero cost,
    just needs `ollama serve` running with a model pulled)

The retry/failover logic below doesn't care which provider is behind each
slot -- it just calls whatever BaseChatModel it was handed.
"""
from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (TimeoutError, ConnectionError, Exception)


def _build_model(provider: str, model_name: str) -> BaseChatModel:
    """Instantiates a chat model for the given provider name."""
    settings = get_settings()

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=settings.groq_api_key,
            model=model_name,
            temperature=0.2,
            timeout=20,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=model_name,
            temperature=0.2,
            # Ollama has no network timeout concept like Groq; local calls
            # can be slow on first load (model needs to be pulled into RAM).
        )

    raise ValueError(f"Unknown model provider: {provider!r} (expected 'groq' or 'ollama')")


class ModelRouter:
    """Calls the primary model; on failure, transparently retries on the
    fallback model. Exposes `.get()` returning something with the same
    `.invoke()`/`.ainvoke()` interface as a normal LangChain chat model, so
    graph nodes never need to know which provider(s) are behind it.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.primary: BaseChatModel = _build_model(settings.primary_provider, settings.primary_model)
        self.fallback: BaseChatModel = _build_model(settings.fallback_provider, settings.fallback_model)
        logger.info(
            "ModelRouter ready: primary=%s/%s fallback=%s/%s",
            settings.primary_provider, settings.primary_model,
            settings.fallback_provider, settings.fallback_model,
        )

    def get(self, structured_schema=None):
        return _FailoverChatModel(self.primary, self.fallback, structured_schema)


class _FailoverChatModel:
    def __init__(self, primary, fallback, structured_schema=None):
        self._primary = primary.with_structured_output(structured_schema) if structured_schema else primary
        self._fallback = fallback.with_structured_output(structured_schema) if structured_schema else fallback

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    )
    def _invoke_primary(self, messages):
        return self._primary.invoke(messages)

    def invoke(self, messages):
        try:
            return self._invoke_primary(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Primary model failed (%s); falling back.", exc)
            self._record_fallback()
            return self._fallback.invoke(messages)

    async def ainvoke(self, messages):
        try:
            return await self._primary.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Primary model failed async (%s); falling back.", exc)
            self._record_fallback()
            return await self._fallback.ainvoke(messages)

    @staticmethod
    def _record_fallback() -> None:
        try:
            from app.observability.metrics import MODEL_FALLBACK_COUNT

            MODEL_FALLBACK_COUNT.inc()
        except Exception:  # noqa: BLE001
            pass


_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
