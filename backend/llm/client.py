"""
Provider-agnostic LLM client.

Works with any OpenAI-compatible endpoint (Groq, OpenAI, Together, DeepSeek,
Anthropic, Gemini, Ollama, Azure) by switching base_url and api_key via env.
Switch providers with LLM_PROVIDER + LLM_API_KEY — no code changes.
"""

import asyncio
import base64
import json
import logging
import re
import time
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI, OpenAI

from config.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_JSON_MODE,
    LLM_PROVIDER,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
    AZURE_API_VERSION,
    VISION_MODEL,
    VISION_API_KEY,
    VISION_BASE_URL,
)
from llm.token_manager import trim_messages

logger = logging.getLogger("voxa.llm.client")

# Providers whose API rejects parameters like top_p
_NO_TOP_P_PROVIDERS = {"anthropic"}

# Context size limits per model tier (chars, ~4 chars/token).
# Primary (llama-3.3-70b-versatile / gpt-4o): 131K-token context → ~524K chars.
# 200K system budget covers the 150K data context plus prompt + history overhead.
_CONTEXT_LIMITS = {
    "primary": {"data": 150_000, "system": 200_000, "max_tokens": 4096},
    "fallback": {"data": 12_000, "system": 16_000, "max_tokens": 1024},
}


def _is_payload_too_large(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "413" in msg or "payload too large" in msg or "request too large" in msg


def _is_rate_limited(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "429" in msg
        or "rate limit" in msg
        or "rate_limit" in msg
        or "ratelimit" in msg
        or "too many requests" in msg
    )


def _build_openai_kwargs() -> dict:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set. "
            "Add it to backend/.env (e.g. LLM_API_KEY=gsk_... for Groq)"
        )
    if LLM_PROVIDER == "azure":
        return {}
    kw: dict = {"api_key": LLM_API_KEY}
    if LLM_BASE_URL:
        kw["base_url"] = LLM_BASE_URL
    return kw


class LLMClient:
    """Thread-safe, provider-agnostic LLM wrapper with fallback support."""

    def __init__(self) -> None:
        self._sync: Optional[OpenAI] = None
        self._async: Optional[AsyncOpenAI] = None
        self._vision_semaphore = asyncio.Semaphore(3)

    # ── Client factories ──────────────────────────────────────────────────────

    def _get_sync(self) -> OpenAI:
        if self._sync is None:
            if LLM_PROVIDER == "azure":
                from openai import AzureOpenAI
                self._sync = AzureOpenAI(
                    api_key=LLM_API_KEY,
                    azure_endpoint=LLM_BASE_URL,
                    api_version=AZURE_API_VERSION,
                )
            else:
                self._sync = OpenAI(**_build_openai_kwargs())
        return self._sync

    def _get_async(self) -> AsyncOpenAI:
        if self._async is None:
            if LLM_PROVIDER == "azure":
                from openai import AsyncAzureOpenAI
                self._async = AsyncAzureOpenAI(
                    api_key=LLM_API_KEY,
                    azure_endpoint=LLM_BASE_URL,
                    api_version=AZURE_API_VERSION,
                )
            else:
                self._async = AsyncOpenAI(**_build_openai_kwargs())
        return self._async

    # ── Payload helpers ───────────────────────────────────────────────────────

    def _chat_kwargs(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        stream: bool = False,
    ) -> dict:
        kw: dict = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if LLM_PROVIDER not in _NO_TOP_P_PROVIDERS:
            kw["top_p"] = 0.9
        return kw

    @staticmethod
    def _limits(model: str) -> dict:
        return (
            _CONTEXT_LIMITS["fallback"]
            if model == FALLBACK_MODEL
            else _CONTEXT_LIMITS["primary"]
        )

    # ── JSON extraction ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    # ── Public API ────────────────────────────────────────────────────────────

    def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        *,
        json_mode: bool = False,
    ) -> str:
        """
        Synchronous completion with automatic fallback on failure.
        Trims messages to stay within context limits.
        """
        target = model or PRIMARY_MODEL
        limits = self._limits(target)
        msgs = trim_messages(messages, limits["system"])

        kw = self._chat_kwargs(target, msgs, limits["max_tokens"])
        if json_mode and LLM_JSON_MODE:
            kw["response_format"] = {"type": "json_object"}

        client = self._get_sync()
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(**kw)
                return resp.choices[0].message.content or ""
            except Exception as exc:
                last_exc = exc
                if _is_rate_limited(exc) and attempt < 2:
                    wait = 2 if attempt == 0 else 5
                    logger.warning(
                        "[LLM] rate limited on %s (attempt %d) — retrying in %ds...",
                        target, attempt + 1, wait,
                    )
                    time.sleep(wait)
                    continue
                break

        exc = last_exc
        if _is_payload_too_large(exc):
            try:
                original_chars = sum(len(m.get("content", "")) for m in messages)
                msgs = trim_messages(messages, limits["system"] // 4)
                trimmed_chars = sum(len(m.get("content", "")) for m in msgs)
                logger.warning(
                    "[LLM] payload too large — trimmed context from %d to %d chars (sync)",
                    original_chars, trimmed_chars,
                )
                resp = client.chat.completions.create(
                    **self._chat_kwargs(target, msgs, min(limits["max_tokens"], 512))
                )
                return resp.choices[0].message.content or ""
            except Exception as exc2:
                if _is_payload_too_large(exc2) and target == PRIMARY_MODEL:
                    logger.warning(
                        f"Compaction retry still too large ({exc2}). Falling back to {FALLBACK_MODEL}..."
                    )
                    return self.complete(messages, FALLBACK_MODEL, json_mode=json_mode)
                raise exc2
        if target == PRIMARY_MODEL:
            logger.warning(f"Primary model failed ({exc}). Trying fallback...")
            return self.complete(messages, FALLBACK_MODEL, json_mode=json_mode)
        logger.error(f"Fallback also failed: {exc}")
        return "I'm sorry, I'm unable to generate a response right now. Please try again in a moment."

    def complete_json(self, messages: list[dict], model: Optional[str] = None) -> dict:
        """Synchronous completion that parses and returns a JSON dict."""
        text = self.complete(messages, model, json_mode=True)
        return self._extract_json(text)

    async def stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async streaming completion. Yields text tokens as they arrive.
        Falls back to the fallback model on primary failure.
        """
        target = model or PRIMARY_MODEL
        limits = self._limits(target)
        msgs = trim_messages(messages, limits["system"])

        client = self._get_async()
        resp = None
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = await client.chat.completions.create(
                    **self._chat_kwargs(target, msgs, limits["max_tokens"], stream=True)
                )
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if _is_rate_limited(exc) and attempt < 2:
                    wait = 2 if attempt == 0 else 5
                    logger.warning(
                        "[LLM] rate limited on %s (attempt %d) — retrying in %ds...",
                        target, attempt + 1, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                break

        if resp is not None:
            try:
                async for chunk in resp:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                return
            except Exception as exc:
                last_exc = exc

        exc = last_exc
        if exc is None:
            return
        if _is_payload_too_large(exc):
            # Aggressive compaction: // 8 keeps the payload under ~10K tokens
            original_chars = sum(len(m.get("content", "")) for m in messages)
            msgs = trim_messages(messages, limits["system"] // 8)
            trimmed_chars = sum(len(m.get("content", "")) for m in msgs)
            logger.warning(
                "[LLM] payload too large — trimmed context from %d to %d chars (stream)",
                original_chars, trimmed_chars,
            )
            try:
                resp = await client.chat.completions.create(
                    **self._chat_kwargs(
                        target, msgs, min(limits["max_tokens"], 512), stream=True
                    )
                )
                async for chunk in resp:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                return
            except Exception as exc2:
                if _is_payload_too_large(exc2) and target == PRIMARY_MODEL:
                    logger.warning(
                        f"Compaction retry still too large ({exc2}). Falling back to {FALLBACK_MODEL}..."
                    )
                    async for token in self.stream(messages, FALLBACK_MODEL):
                        yield token
                    return
                logger.error("Compacted request also failed: %s", exc2)
                yield "\n\n⚠️ Response too large to generate. Try a more specific question."
                return
        if target == PRIMARY_MODEL:
            logger.warning(f"Primary stream failed ({exc}). Trying fallback...")
            async for token in self.stream(messages, FALLBACK_MODEL):
                yield token
        else:
            logger.error(f"Fallback stream also failed: {exc}")
            yield f"\n\n⚠️ Error generating response: {exc}"

    async def complete_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str = "image/jpeg",
        model: Optional[str] = None,
    ) -> str:
        """
        Send an image + prompt to a vision-capable model and return the text response.
        Uses a Semaphore(3) to cap concurrent vision calls and avoid per-second rate limits.
        Falls back to LLM_API_KEY / LLM_BASE_URL when no separate vision credentials are set.
        """
        target = model or VISION_MODEL or PRIMARY_MODEL
        effective_key = VISION_API_KEY or LLM_API_KEY
        effective_url = VISION_BASE_URL or LLM_BASE_URL

        # Build a separate client only when vision credentials differ from chat credentials
        if (VISION_API_KEY and VISION_API_KEY != LLM_API_KEY) or \
           (VISION_BASE_URL and VISION_BASE_URL != LLM_BASE_URL):
            vision_client = AsyncOpenAI(
                api_key=effective_key,
                base_url=effective_url or None,
            )
        else:
            vision_client = self._get_async()

        b64 = base64.b64encode(image_bytes).decode()
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }]

        async with self._vision_semaphore:
            resp = await vision_client.chat.completions.create(
                model=target,
                messages=messages,
                max_tokens=1024,
                temperature=0.0,
            )
            return resp.choices[0].message.content or ""

    def health_check(self) -> dict:
        """Ping the LLM provider and return status info."""
        try:
            self.complete([{"role": "user", "content": "Say OK"}])
            return {
                "status": "healthy",
                "provider": LLM_PROVIDER,
                "primary_model": PRIMARY_MODEL,
                "fallback_model": FALLBACK_MODEL,
            }
        except Exception as exc:
            return {
                "status": "error",
                "provider": LLM_PROVIDER,
                "error": str(exc),
                "primary_model": PRIMARY_MODEL,
                "fallback_model": FALLBACK_MODEL,
            }


# ── Singleton ─────────────────────────────────────────────────────────────────
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
