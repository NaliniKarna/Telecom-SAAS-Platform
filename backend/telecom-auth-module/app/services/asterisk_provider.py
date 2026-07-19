"""Asterisk provider abstraction (telephony integration layer).

Mirrors the SmsProvider seam: the service layer depends ONLY on the
`AsteriskProvider` protocol and the `get_asterisk_provider()` factory — never on
a concrete client. Today the factory returns `NullAsteriskProvider` (simulation):
it reports connections as reachable and accepts originate requests without any
network I/O, so the whole integration layer runs end to end WITHOUT a real PBX.

`AmiAsteriskProvider` is the real adapter (Asterisk Manager Interface via
panoramisk). It is implemented and ready; switch it on by setting
TELEPHONY_PROVIDER=ami once a PBX is reachable — no service/route/UI change.

Phase 3 uses get_status() (connection health). originate() and parse_event()
are the seams Voice (Phase 5) and Missed Call (Phase 6) will build on; they are
defined here so those phases plug in without reshaping this layer.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ConnectionParams:
    """Resolved, decrypted connection parameters handed to a provider."""
    host: str
    port: int
    username: str
    secret: str
    use_tls: bool = False
    timeout: int = 5


@dataclass
class ConnectionStatus:
    """Outcome of a health/reachability check against a PBX."""
    connected: bool
    detail: str = ""
    latency_ms: int | None = None
    provider: str = ""


@dataclass
class OriginateResult:
    """Outcome of requesting an outbound call. (Seam for Phase 5/6.)"""
    accepted: bool
    action_id: str | None = None
    error: str | None = None


@dataclass
class TelephonyEvent:
    """Normalized telephony event (CDR / channel state) ingested from a PBX.
    (Seam for Phase 5/6 — no ingestion pipeline is wired in Phase 3.)"""
    event_type: str
    channel: str | None = None
    caller_id: str | None = None
    extension: str | None = None
    raw: dict = field(default_factory=dict)


class AsteriskProvider(Protocol):
    """Interface every Asterisk client adapter implements."""
    name: str

    async def get_status(self, params: ConnectionParams) -> ConnectionStatus:
        ...

    async def originate(
        self, params: ConnectionParams, *, channel: str, extension: str,
        caller_id: str | None = None, context: str = "from-internal",
    ) -> OriginateResult:
        ...

    def parse_event(self, payload: dict) -> "TelephonyEvent | None":
        ...


class NullAsteriskProvider:
    """Simulation provider used for development/testing. No network I/O."""
    name = "null"

    async def get_status(self, params: ConnectionParams) -> ConnectionStatus:
        # A simulated bind always "succeeds" as long as params look complete,
        # so the integration layer is exercisable without a PBX.
        if not params.host or not params.username:
            return ConnectionStatus(
                connected=False, detail="Missing host/username", provider=self.name
            )
        return ConnectionStatus(
            connected=True, detail="Simulated AMI bind OK", latency_ms=0,
            provider=self.name,
        )

    async def originate(self, params, *, channel, extension, caller_id=None,
                        context="from-internal") -> OriginateResult:
        return OriginateResult(accepted=True, action_id=f"sim-{uuid.uuid4().hex}")

    def parse_event(self, payload: dict) -> "TelephonyEvent | None":
        et = payload.get("event") or payload.get("Event")
        if not et:
            return None
        return TelephonyEvent(
            event_type=et,
            channel=payload.get("channel") or payload.get("Channel"),
            caller_id=payload.get("caller_id") or payload.get("CallerIDNum"),
            extension=payload.get("extension") or payload.get("Exten"),
            raw=payload,
        )


class AmiAsteriskProvider:
    """Real adapter: Asterisk Manager Interface via panoramisk.

    Implemented and ready; not the default. `panoramisk` is imported lazily so
    the dependency is only required when TELEPHONY_PROVIDER=ami is actually
    selected (the simulation path never imports it).
    """
    name = "ami"

    async def get_status(self, params: ConnectionParams) -> ConnectionStatus:
        start = time.monotonic()
        try:
            from panoramisk import Manager  # lazy import
        except ImportError:
            return ConnectionStatus(
                connected=False,
                detail="panoramisk not installed (pip install panoramisk)",
                provider=self.name,
            )
        manager = Manager(
            host=params.host, port=params.port,
            username=params.username, secret=params.secret,
            ssl=params.use_tls, connection_timeout=params.timeout,
        )
        try:
            await manager.connect()
            res = await manager.send_action({"Action": "Ping"})
            ok = bool(res) and getattr(res, "Response", None) in ("Success", "Pong")
            latency = int((time.monotonic() - start) * 1000)
            return ConnectionStatus(
                connected=ok,
                detail="AMI Ping OK" if ok else "AMI Ping failed",
                latency_ms=latency, provider=self.name,
            )
        except Exception as exc:  # noqa: BLE001 — surface any bind/login error
            return ConnectionStatus(
                connected=False, detail=f"{type(exc).__name__}: {exc}",
                provider=self.name,
            )
        finally:
            try:
                manager.close()
            except Exception:  # noqa: BLE001
                pass

    async def originate(self, params, *, channel, extension, caller_id=None,
                        context="from-internal") -> OriginateResult:
        try:
            from panoramisk import Manager  # lazy import
        except ImportError:
            return OriginateResult(accepted=False, error="panoramisk not installed")
        manager = Manager(
            host=params.host, port=params.port,
            username=params.username, secret=params.secret,
            ssl=params.use_tls, connection_timeout=params.timeout,
        )
        action_id = uuid.uuid4().hex
        try:
            await manager.connect()
            action = {
                "Action": "Originate", "Channel": channel, "Exten": extension,
                "Context": context, "Priority": "1", "ActionID": action_id,
                "Async": "true",
            }
            if caller_id:
                action["CallerID"] = caller_id
            res = await manager.send_action(action)
            ok = getattr(res, "Response", None) in ("Success", "Accepted")
            return OriginateResult(
                accepted=ok, action_id=action_id,
                error=None if ok else "Originate not accepted",
            )
        except Exception as exc:  # noqa: BLE001
            return OriginateResult(accepted=False, error=f"{type(exc).__name__}: {exc}")
        finally:
            try:
                manager.close()
            except Exception:  # noqa: BLE001
                pass

    def parse_event(self, payload: dict) -> "TelephonyEvent | None":
        et = payload.get("Event")
        if not et:
            return None
        return TelephonyEvent(
            event_type=et, channel=payload.get("Channel"),
            caller_id=payload.get("CallerIDNum"), extension=payload.get("Exten"),
            raw=payload,
        )


_provider: AsteriskProvider | None = None


def get_asterisk_provider() -> AsteriskProvider:
    """Single place that decides which Asterisk client is active, driven by
    settings.TELEPHONY_PROVIDER ("null" | "ami"). Cached per process."""
    global _provider
    if _provider is None:
        from app.core.config import settings
        from app.core.constants import TelephonyProvider
        if settings.TELEPHONY_PROVIDER == TelephonyProvider.AMI.value:
            _provider = AmiAsteriskProvider()
        else:
            _provider = NullAsteriskProvider()
    return _provider


def reset_asterisk_provider() -> None:
    """Test hook to clear the cached provider."""
    global _provider
    _provider = None
