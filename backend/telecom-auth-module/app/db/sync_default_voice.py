"""Sync the default global ElevenLabs voice's provider_voice_id with settings.

This is what "wires ELEVENLABS_DEFAULT_VOICE_ID to the env" actually means in
this codebase: the value ElevenLabs is called with lives on the `ai_voices`
DB row (`provider_voice_id`), not read fresh from settings on every request.
Before this module existed, changing ELEVENLABS_DEFAULT_VOICE_ID in `.env`
did nothing — the setting was defined but never consulted anywhere. Now,
on every app startup, the ONE seeded default voice row (identified by the
fixed id migration 0028 created it with — never by name, since an admin
could rename it) gets its `provider_voice_id` updated to match the current
setting if they've drifted apart. Change the env var, restart the backend,
done — no manual SQL.

Deliberately narrow:
- Only touches that one seeded row. Never creates new voices, never touches
  company-owned voices, never touches any voice an admin created by hand.
- Only runs when TTS_PROVIDER=elevenlabs (nothing meaningful to sync
  otherwise).
- Never raises. This is a startup convenience, not a required step — if
  migration 0028 hasn't been applied yet (table/row doesn't exist) or
  anything else goes wrong, this logs and gets out of the way rather than
  blocking the app from booting.
"""
import logging
import uuid

from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Fixed id migration 0028 seeds the default voice row with — see
# alembic/versions/0028_ai_voice_tts_foundation.py::_SEED_VOICE_ID.
_DEFAULT_VOICE_ID = uuid.UUID("b2a1c9d0-6e3f-4a11-9c2e-8f7d5a0b1e4c")


async def sync_default_elevenlabs_voice() -> None:
    if settings.TTS_PROVIDER != "elevenlabs":
        return

    try:
        from app.models.ai_voice import AiVoice  # local import: table may not exist yet

        async with AsyncSessionLocal() as session:
            voice = await session.get(AiVoice, _DEFAULT_VOICE_ID)
            if voice is None:
                return
            if voice.provider_voice_id != settings.ELEVENLABS_DEFAULT_VOICE_ID:
                old = voice.provider_voice_id
                voice.provider_voice_id = settings.ELEVENLABS_DEFAULT_VOICE_ID
                await session.commit()
                logger.info(
                    "Synced default ElevenLabs voice provider_voice_id: %s -> %s",
                    old, settings.ELEVENLABS_DEFAULT_VOICE_ID,
                )
    except Exception:  # noqa: BLE001 — startup convenience must never block boot
        logger.exception("sync_default_elevenlabs_voice failed; continuing startup")