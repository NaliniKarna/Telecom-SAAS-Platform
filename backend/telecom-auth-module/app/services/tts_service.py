"""TTS Service — the one place that turns text into a stored, playable audio
file. Provider-agnostic (see app.services.tts_provider) and storage-agnostic
(see app.core.storage): swapping either requires no change here.

Pipeline (matches the spec's required flow exactly):
  1. Receive text (already rendered — this module doesn't know about
     templates or variables, see app.services.ai_voice_service for that).
  2. Call the configured TTS provider.
  3. Receive generated audio.
  4. Optionally normalize for PBX/telephony compatibility (kept as a
     DISTINCT step from provider output handling, per the spec — see
     `_normalize_for_telephony` below).
  5. Store the audio via the EXISTING FileStorage abstraction.
  6. Return a stable URL plus best-effort duration.

Callable programmatically (no HTTP/route dependency) — this is what a future
Voice Campaign worker will call directly, per the spec's integration
boundary.
"""
from __future__ import annotations

import io
import logging
import wave
from dataclasses import dataclass

from app.core.config import settings
from app.core.storage import get_storage
from app.services.tts_provider import TTSProvider, get_tts_provider

logger = logging.getLogger(__name__)


@dataclass
class TTSSynthesisResult:
    audio_url: str
    content_type: str
    char_count: int
    duration_seconds: int | None


def _wav_duration_seconds(audio_bytes: bytes) -> int | None:
    """Best-effort duration for WAV audio using the stdlib `wave` module (no
    extra dependency). Returns None for non-WAV formats (e.g. ElevenLabs'
    MP3 output) rather than guessing — a wrong duration is worse than a
    missing one."""
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return int(frames / rate) if rate else None
    except (wave.Error, EOFError):
        return None


def _normalize_for_telephony(audio_bytes: bytes, content_type: str) -> tuple[bytes, str]:
    """Convert provider output to a telephony-compatible format (8kHz mono
    16-bit PCM WAV is the common Asterisk/FreePBX baseline) when
    settings.TTS_NORMALIZE_FOR_TELEPHONY is enabled.

    Deliberately OFF by default and deliberately a separate step from
    provider output handling (per spec) — this phase stops at preview
    generation, and real transcoding needs ffmpeg available on the host
    (via the `pydub` package) which is not something to silently require.
    When a future phase actually dispatches audio to Asterisk, enable this
    flag once ffmpeg is confirmed present; until then previews are stored
    in whatever format the provider returned (WAV for the Null provider,
    MP3 for ElevenLabs) and playback works fine in the browser either way.
    """
    if not settings.TTS_NORMALIZE_FOR_TELEPHONY:
        return audio_bytes, content_type

    try:
        from pydub import AudioSegment  # optional dependency, ffmpeg-backed
    except ImportError as exc:
        raise RuntimeError(
            "TTS_NORMALIZE_FOR_TELEPHONY is enabled but the 'pydub' package "
            "(and a system ffmpeg binary) is not available. Install pydub "
            "and ffmpeg, or disable TTS_NORMALIZE_FOR_TELEPHONY."
        ) from exc

    fmt = "wav" if "wav" in content_type else "mp3"
    segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
    segment = segment.set_frame_rate(8000).set_channels(1).set_sample_width(2)
    out = io.BytesIO()
    segment.export(out, format="wav")
    return out.getvalue(), "audio/wav"


class TTSService:
    def __init__(self, provider: TTSProvider | None = None):
        self.provider = provider or get_tts_provider()
        self.storage = get_storage()

    def synthesize_and_store(
        self, *, text: str, provider_voice_id: str, model_id: str | None = None,
        storage_prefix: str = "tts",
    ) -> TTSSynthesisResult:
        result = self.provider.synthesize(
            text=text, provider_voice_id=provider_voice_id, model_id=model_id,
        )
        audio_bytes, content_type = _normalize_for_telephony(
            result.audio_bytes, result.content_type,
        )

        ext = "wav" if "wav" in content_type else "mp3"
        filename = f"preview.{ext}"
        audio_url = self.storage.save(
            data=audio_bytes, filename=filename, content_type=content_type,
            prefix=storage_prefix,
        )

        duration = _wav_duration_seconds(audio_bytes) if "wav" in content_type else None

        return TTSSynthesisResult(
            audio_url=audio_url,
            content_type=content_type,
            char_count=len(text),
            duration_seconds=duration,
        )
