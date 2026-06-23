"""
Speech router — audio-to-text transcription.
"""

import logging
from fastapi import APIRouter, File, HTTPException, UploadFile

from services.stt_service import transcribe_audio

router = APIRouter()
logger = logging.getLogger("voxa.router.speech")


@router.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """
    Accept an audio file and return its transcription.

    Response: {"text": str, "confidence": float, "language": str}
    """
    if not audio:
        raise HTTPException(status_code=400, detail="No audio file provided")

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    logger.info(f"Transcribing {len(content)} bytes from '{audio.filename}'")
    result = await transcribe_audio(content, audio.filename or "recording.webm")

    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])

    return result
