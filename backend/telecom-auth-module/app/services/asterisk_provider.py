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
class OriginatePlaybackParams:
    """Everything a provider needs to originate a call and play a
    pre-generated audio file to it (Phase 4B — Voice Campaign execution).
    audio_reference is a stable URI/path the provider resolves at call time,
    NEVER raw audio bytes (spec: 'do not put audio binaries into Kafka' and,
    by the same logic, never pass them through this call either — audio
    lives in storage, this just points at it)."""
    destination_e164: str
    audio_reference: str
    campaign_id: str
    recipient_id: str
    correlation_id: str  # the attempt's execution_key — idempotency anchor
    caller_id: str | None = None


@dataclass
class OriginatePlaybackResult:
    """Outcome of one originate_playback() call.

    final_status, when set, is one of VoiceCampaignRecipientStatus's terminal
    values (ANSWERED-then-COMPLETED collapses to "completed" here since the
    caller only needs the recipient's eventual status) — this provider
    already knows, synchronously, how the whole call turned out. Only the
    Null/Simulator provider can honestly set this today: it fabricates the
    entire call lifecycle deterministically. The real AMI provider leaves
    this None — it can confirm the origination was accepted, but has no
    event listener wired up (yet) to observe Answer/Hangup/PlaybackComplete,
    so it cannot honestly claim to know the outcome (spec: 'do not fake a
    successful real AMI call' / 'keep the state model honest'). Callers must
    treat final_status=None as 'still calling, outcome unknown' — not as a
    failure and not as success.
    """
    accepted: bool
    action_id: str | None = None
    final_status: str | None = None
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

    async def originate_playback(
        self, params: ConnectionParams, playback: OriginatePlaybackParams,
    ) -> OriginatePlaybackResult:
        """Outbound call + audio playback (Phase 4B — Voice Campaign
        execution). A distinct capability from originate(): that method
        dials an extension/channel inside the PBX; this one places an
        OUTBOUND call to an external E.164 number and plays a specific
        pre-generated file to whoever (or whatever) answers."""
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

    # Deterministic test hooks: a destination E.164 number ending in one of
    # these suffixes simulates that specific non-success outcome instead of
    # the default success, so tests can exercise every branch of the
    # recipient state machine without any randomness. Ordinary Nepal mobile
    # numbers essentially never end in these four-digit sequences by chance,
    # so this is safe outside tests too. Documented here rather than hidden
    # in a hash so a reader of a failing test can see exactly why.
    _SIMULATE_NO_ANSWER_SUFFIX = "0000"
    _SIMULATE_BUSY_SUFFIX = "9999"
    _SIMULATE_FAILURE_SUFFIX = "6666"

    async def originate_playback(
        self, params: ConnectionParams, playback: OriginatePlaybackParams,
    ) -> OriginatePlaybackResult:
        # No network I/O at all — the whole call lifecycle (originate,
        # answer, play, hang up) is fabricated synchronously and
        # deterministically, which is exactly what makes this provider
        # suitable for automated tests without a real PBX.
        action_id = f"sim-{uuid.uuid4().hex}"
        dest = playback.destination_e164

        if dest.endswith(self._SIMULATE_FAILURE_SUFFIX):
            return OriginatePlaybackResult(
                accepted=False, action_id=action_id,
                error="Simulated origination failure (test suffix 6666)",
            )
        if dest.endswith(self._SIMULATE_NO_ANSWER_SUFFIX):
            return OriginatePlaybackResult(
                accepted=True, action_id=action_id, final_status="no_answer",
            )
        if dest.endswith(self._SIMULATE_BUSY_SUFFIX):
            return OriginatePlaybackResult(
                accepted=True, action_id=action_id, final_status="busy",
            )
        return OriginatePlaybackResult(
            accepted=True, action_id=action_id, final_status="completed",
        )

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
            from panoramisk import Manager  # type: ignore[import-not-found]  # lazy import; optional dependency
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
            from panoramisk import Manager  # type: ignore[import-not-found]  # lazy import; optional dependency
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

    async def originate_playback(
        self, params: ConnectionParams, playback: OriginatePlaybackParams,
    ) -> OriginatePlaybackResult:
        """Honest, PARTIAL real-AMI implementation — see the module and
        OriginatePlaybackResult docstrings. Two deployment-specific gaps
        this method cannot solve from inside a generic provider seam
        (documented here, and in IMPLEMENTATION-REPORT.md, rather than
        silently pretending they work):

        1. Outbound channel string. Dialing an external E.164 number
           requires a trunk-specific channel (e.g. "SIP/my-trunk/<number>"
           or a dialplan-specific "Local/<number>@outbound-context"), and
           TelephonyConnection has no trunk-name field today — only AMI
           host/port/credentials. Falls back to Local/<number>@from-internal
           (the same default context originate() already assumes), which
           will only actually place an external call if the target
           Asterisk's dialplan happens to route that context to a trunk for
           E.164-looking extensions. A real deployment will very likely need
           a configurable trunk/context field added to TelephonyConnection —
           not invented here since that's a schema/UI decision outside this
           phase's scope.
        2. Audio file transport. Asterisk's Playback() application expects
           a filename it can read from ITS OWN local sound-file storage, not
           an arbitrary HTTP URL — so playback.audio_reference (a FileStorage
           URL, per this phase's storage abstraction) cannot be handed to
           Playback() as-is on a real box. This is exactly the "PBX audio
           handoff" gap Phase 4A's VoiceCampaignAudio.pbx_reachable flag
           already flags (defaults False) and Phase 4B does not solve either
           — a real deployment needs an explicit transfer step (e.g. SFTP/
           rsync the file to the PBX's sounds directory, or an Asterisk
           module that can fetch over HTTP) before this Data value means
           anything to a real Asterisk instance.

        Given both gaps, this method still attempts the AMI Originate action
        (so the seam is real, not stubbed out) but honestly leaves
        final_status=None always — there is no AMI event listener wired up
        here to observe Answer/Hangup/PlaybackComplete, so beyond "was the
        action itself accepted by AMI", nothing about the call's outcome can
        be honestly reported (spec: "do not fake a successful real AMI
        call"). A real deployment needs an AMI event-listener process
        (subscribing to Newstate/Hangup/PlaybackComplete-equivalent events,
        correlating them back to this action_id) to ever advance a
        real-provider recipient past CALLING.
        """
        try:
            # Load the optional AMI dependency dynamically so static analyzers
            # do not require it to be installed for the rest of the module.
            from importlib import import_module

            Manager = import_module("panoramisk").Manager
        except ImportError:
            return OriginatePlaybackResult(accepted=False, error="panoramisk not installed")
        manager = Manager(
            host=params.host, port=params.port,
            username=params.username, secret=params.secret,
            ssl=params.use_tls, connection_timeout=params.timeout,
        )
        action_id = uuid.uuid4().hex
        try:
            await manager.connect()
            action = {
                "Action": "Originate",
                "Channel": f"Local/{playback.destination_e164}@from-internal",
                "Application": "Playback",
                "Data": playback.audio_reference,
                "ActionID": action_id,
                "Async": "true",
            }
            if playback.caller_id:
                action["CallerID"] = playback.caller_id
            res = await manager.send_action(action)
            ok = getattr(res, "Response", None) in ("Success", "Accepted")
            return OriginatePlaybackResult(
                accepted=ok, action_id=action_id, final_status=None,
                error=None if ok else "Originate not accepted",
            )
        except Exception as exc:  # noqa: BLE001
            return OriginatePlaybackResult(
                accepted=False, action_id=action_id, error=f"{type(exc).__name__}: {exc}",
            )
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
