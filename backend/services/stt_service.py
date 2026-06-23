"""
Speech-to-text service.
Uses the same provider configured in LLM_PROVIDER (Groq or OpenAI both expose
a Whisper-compatible audio/transcriptions endpoint).
"""

import logging

from config.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_PROVIDER,
    STT_MODEL,
    STT_AVAILABLE,
    AZURE_API_VERSION,
)

logger = logging.getLogger("voxa.stt")

_client = None


def _get_client():
    global _client
    if _client is None:
        if not STT_AVAILABLE:
            raise ValueError(
                f"Provider '{LLM_PROVIDER}' does not support audio transcription. "
                "Use groq or openai, or set LLM_SUPPORTS_STT=true in .env."
            )
        if not LLM_API_KEY:
            raise ValueError("LLM_API_KEY is not set — voice-to-text will not work.")

        if LLM_PROVIDER == "azure":
            from openai import AzureOpenAI
            _client = AzureOpenAI(
                api_key=LLM_API_KEY,
                azure_endpoint=LLM_BASE_URL,
                api_version=AZURE_API_VERSION,
            )
        else:
            from openai import OpenAI
            kwargs: dict = {"api_key": LLM_API_KEY}
            if LLM_BASE_URL:
                kwargs["base_url"] = LLM_BASE_URL
            _client = OpenAI(**kwargs)

        logger.info(f"STT client initialised (provider={LLM_PROVIDER}, model={STT_MODEL})")
    return _client


def init_stt_service() -> None:
    """Log STT availability at startup — does not eagerly create the client."""
    if not STT_AVAILABLE:
        logger.warning(f"STT not available for provider '{LLM_PROVIDER}' — voice-to-text disabled")
    elif not LLM_API_KEY:
        logger.warning("LLM_API_KEY not set — STT will fail on first use")
    else:
        logger.info(f"STT ready (provider={LLM_PROVIDER}, model={STT_MODEL})")


async def transcribe_audio(audio_bytes: bytes, filename: str = "recording.webm") -> dict:
    """
    Transcribe *audio_bytes* using the configured STT provider.
    Returns {"text": str, "confidence": float, "language": str}.
    """
    try:
        client = _get_client()
    except ValueError as exc:
        logger.error(f"STT init error: {exc}")
        return {"text": "", "error": str(exc), "confidence": 0.0, "language": "en"}

    try:
        logger.info(f"Transcribing {len(audio_bytes)} bytes via {LLM_PROVIDER}…")
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=STT_MODEL,
            response_format="json",
            language="en",
            temperature=0.0,
        )
        text = (transcription.text or "").strip()
        if not text:
            logger.warning("Empty transcription returned")
            return {"text": "", "confidence": 0.0, "language": "en"}
        logger.info(f"Transcribed: '{text[:80]}…'")
        return {"text": text, "confidence": 1.0, "language": "en"}
    except Exception as exc:
        logger.error(f"Transcription failed: {exc}")
        return {"text": "", "error": f"Transcription failed: {exc}", "confidence": 0.0, "language": "en"}
