"""ElevenLabs TTS provider.

Adapted from the working `nepali-tts` reference project's call shape:

    client.text_to_speech.convert(
        text=text, voice_id=VOICE_ID, model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={"stability": 0.5, "similarity_boost": 0.75,
                         "style": 0.2, "use_speaker_boost": True},
    )

That reference used the `elevenlabs` PyPI SDK. This provider does not depend
on it — it calls the same REST endpoint directly with `httpx`, matching how
every other external integration in this codebase talks to its provider
(see app/services/akashsms_provider.py). One fewer third-party dependency,
same wire behavior.

Deliberately NOT carried over from the reference: the CLI input loop, local
playback (`elevenlabs.play`), `.env`-based config outside the app's own
Settings, and timestamp-based standalone file naming — audio here is handed
back as raw bytes to the caller, which is responsible for storage (see
app.services.tts_service).
"""
from __future__ import annotations

import logging

import httpx

from app.services.tts_provider import TTSResult

logger = logging.getLogger(__name__)

# Same defaults the reference project used — smoother/more natural speech
# for the multilingual model. Not currently exposed as settings since
# nothing in this phase needs per-request tuning; revisit if/when Voice
# Campaigns need per-template voice_settings control.
_DEFAULT_VOICE_SETTINGS = {
  "stability": 0.5,
  "similarity_boost": 0.75,
  "style": 0,
  "use_speaker_boost": True,
  "speed": 0.95
}


class ElevenLabsProviderError(RuntimeError):
    """Raised when the ElevenLabs API call fails or is misconfigured.

    status_code distinguishes transient from permanent failures for
    Phase 4B's worker retry classification (app.workers.voice_campaign_worker
    ._is_transient_tts_error): None (a network-level httpx.HTTPError, no
    response at all) or >=500 is treated as transient/worth retrying; a 4xx
    response (bad request, 401/402/403 auth or billing, 422 validation) is
    permanent — retrying the exact same request won't fix it.
    """

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ElevenLabsTTSProvider:
    name = "elevenlabs"

    def __init__(self, *, api_key: str, base_url: str, default_model_id: str, timeout: float = 30.0):
        if not api_key:
            # Fail at construction, not on first request — the factory in
            # tts_provider.py only reaches here when TTS_PROVIDER=elevenlabs,
            # so a missing key at that point is a real misconfiguration.
            raise ElevenLabsProviderError(
                "TTS_PROVIDER=elevenlabs but ELEVENLABS_API_KEY is not set"
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model_id = default_model_id
        self._timeout = timeout

    def synthesize(self, *, text: str, provider_voice_id: str, model_id: str | None = None) -> TTSResult:
        url = f"{self._base_url}/v1/text-to-speech/{provider_voice_id}"
        payload = {
            "text": text,
            "model_id": model_id or self._default_model_id,
            "voice_settings": _DEFAULT_VOICE_SETTINGS,
        }
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            logger.error("elevenlabs_request_failed", extra={"error": str(exc)})
            raise ElevenLabsProviderError(f"ElevenLabs request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            logger.error(
                "elevenlabs_error_response",
                extra={"status": response.status_code, "detail": detail},
            )
            raise ElevenLabsProviderError(
                f"ElevenLabs returned {response.status_code}: {detail}",
                status_code=response.status_code,
            )

        return TTSResult(
            audio_bytes=response.content,
            content_type=response.headers.get("content-type", "audio/mpeg"),
            provider_reference=response.headers.get("request-id"),
        )
