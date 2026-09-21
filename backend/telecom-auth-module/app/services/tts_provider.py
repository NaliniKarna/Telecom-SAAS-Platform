"""TTS provider abstraction (gateway-agnostic speech synthesis).

Mirrors app.services.sms_provider exactly on purpose: same shape (Protocol +
dataclass result + Null simulation provider + settings-driven factory), so
anyone already familiar with the SMS provider pattern already knows this one.

The Voice Template / TTS service depends ONLY on the `TTSProvider` protocol
and `get_tts_provider()` — never on a concrete vendor. Adding a local Nepali
TTS provider later means writing one new class and adding one branch to the
factory; nothing in ai_voice_service.py or the API layer changes.

Providers:
  NullTTSProvider        — simulation (writes a tiny silent WAV, no network
                            I/O, no API key required). Default.
  ElevenLabsTTSProvider  — production bridge to the ElevenLabs API.

The factory reads settings.TTS_PROVIDER to decide which is active.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Protocol


@dataclass
class TTSResult:
    """Outcome of one text-to-speech synthesis call."""
    audio_bytes: bytes
    content_type: str
    provider_reference: str | None = None


class TTSProvider(Protocol):
    """Interface every speech-synthesis backend implements."""
    name: str

    def synthesize(self, *, text: str, provider_voice_id: str, model_id: str | None = None) -> TTSResult:
        ...


def _silent_wav(seconds: float = 0.5, sample_rate: int = 8000) -> bytes:
    """A minimal, valid, silent mono 16-bit PCM WAV file.

    Used by NullTTSProvider so the whole pipeline (storage, URL, frontend
    audio player) can be exercised end-to-end with zero external
    dependencies and zero cost during development/testing.
    """
    n_samples = int(seconds * sample_rate)
    data = b"\x00\x00" * n_samples
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(data)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", len(data)))
    buf.write(data)
    return buf.getvalue()


class NullTTSProvider:
    """Simulation provider. No network I/O, no API key needed."""
    name = "null"

    def synthesize(self, *, text: str, provider_voice_id: str, model_id: str | None = None) -> TTSResult:
        # Length scales trivially with text so previews of different lengths
        # are at least visibly different durations, without pretending to be
        # real speech.
        seconds = max(0.3, min(len(text) / 15.0, 8.0))
        return TTSResult(
            audio_bytes=_silent_wav(seconds=seconds),
            content_type="audio/wav",
            provider_reference=f"sim-{provider_voice_id}",
        )


_provider: TTSProvider | None = None


def get_tts_provider() -> TTSProvider:
    """Factory that returns the active TTS provider based on settings.

    "null"       -> NullTTSProvider (default, no synthesis, no API key)
    "elevenlabs" -> ElevenLabsTTSProvider (calls the ElevenLabs API)
    """
    global _provider
    if _provider is None:
        from app.core.config import settings

        if settings.TTS_PROVIDER == "elevenlabs":
            from app.services.elevenlabs_provider import ElevenLabsTTSProvider
            _provider = ElevenLabsTTSProvider(
                api_key=settings.ELEVENLABS_API_KEY,
                base_url=settings.ELEVENLABS_API_BASE_URL,
                default_model_id=settings.ELEVENLABS_MODEL_ID,
            )
        else:
            _provider = NullTTSProvider()

    return _provider
