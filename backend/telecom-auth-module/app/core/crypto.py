"""Symmetric encryption for secrets stored at rest (e.g. AMI passwords).

Telephony connection secrets must not be stored in plaintext. We use Fernet
(AES-128-CBC + HMAC) with a key derived from settings, so the database never
holds a usable secret on its own. The key comes from TELEPHONY_SECRET_KEY when
set; otherwise it is derived from JWT_SECRET_KEY so local/dev works without extra
configuration. In production, set a dedicated TELEPHONY_SECRET_KEY.

Swap this module for a KMS/secrets-manager backend later without touching
callers — the encrypt()/decrypt() contract stays the same.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    raw = getattr(settings, "TELEPHONY_SECRET_KEY", "") or settings.JWT_SECRET_KEY
    # Derive a stable 32-byte urlsafe key from whatever secret we were given.
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Returns an opaque urlsafe token string."""
    if plaintext is None:
        raise ValueError("Cannot encrypt None")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt a stored secret. Raises ValueError if the token is invalid
    (e.g. the encryption key changed)."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Stored secret could not be decrypted") from exc
