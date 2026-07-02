"""File storage abstraction (provider-agnostic).

The rest of the app depends only on the `FileStorage` protocol and the
`get_storage()` factory — it never imports a concrete backend. Today the factory
returns the local-disk backend (dev/simple deployments). To move to S3, MinIO,
or Cloudflare R2 later, implement a new backend with the same `save()` contract
and switch the factory; no caller, route, or UI changes are needed.

`save()` returns a PUBLIC URL string. That URL is what gets persisted on the
model (e.g. Company.logo_url), so the database is already storage-agnostic.
"""
import os
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class FileStorage(Protocol):
    def save(self, *, data: bytes, filename: str, content_type: str,
             prefix: str = "") -> str:
        """Persist bytes and return a public URL to retrieve them."""
        ...


class LocalDiskStorage:
    """Writes under settings.UPLOAD_DIR and serves via settings.UPLOAD_URL_BASE.

    The app must mount UPLOAD_DIR as static files at UPLOAD_URL_BASE (done in
    main.py). Intended for local/dev; swap for an object-store backend in prod.
    """

    def __init__(self, base_dir: str, url_base: str):
        self.base_dir = Path(base_dir)
        self.url_base = url_base.rstrip("/")

    def save(self, *, data: bytes, filename: str, content_type: str,
             prefix: str = "") -> str:
        ext = os.path.splitext(filename)[1].lower() or _ext_for(content_type)
        key = f"{uuid.uuid4().hex}{ext}"
        rel = f"{prefix.strip('/')}/{key}" if prefix else key
        dest = self.base_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return f"{self.url_base}/{rel}"


def _ext_for(content_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "image/gif": ".gif",
    }.get(content_type, "")


_storage: FileStorage | None = None


def get_storage() -> FileStorage:
    """Factory — the single place that knows which backend is active."""
    global _storage
    if _storage is None:
        _storage = LocalDiskStorage(
            base_dir=settings.UPLOAD_DIR,
            url_base=settings.UPLOAD_URL_BASE,
        )
    return _storage
