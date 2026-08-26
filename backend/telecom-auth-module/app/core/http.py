"""Small HTTP helpers shared across the API layer.

Kept separate from app.core.security (crypto) and app.api.v1.deps (DI wiring)
so both route modules and dependency functions can import it without
introducing a routes -> deps -> routes cycle.
"""
from fastapi import Request

from app.core.config import settings


def client_ip(request: Request) -> str | None:
    """Caller IP for audit trails, the API-key IP whitelist, and rate limits.

    X-Forwarded-For is attacker-controlled input: any client can set it to
    whatever it likes. It is only safe to read once you know how many
    reverse proxies sit in front of the app and therefore how many hops of
    the header are proxy-appended (trustworthy) versus attacker-supplied.

    settings.TRUSTED_PROXY_HOPS controls this and defaults to 0 — meaning
    the header is ignored entirely and the raw socket peer is used. That is
    the only safe default for a deployment where the app might be directly
    internet-facing. Only raise it once you've confirmed the real proxy
    topology (each hop should append exactly one address to the header).

    With N trusted hops, the real client is the Nth entry counting from the
    right of the chain — anything to its left could have been forged by the
    client itself.
    """
    hops = settings.TRUSTED_PROXY_HOPS
    if hops > 0:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            chain = [p.strip() for p in fwd.split(",") if p.strip()]
            if len(chain) >= hops:
                return chain[-hops]
    return request.client.host if request.client else None