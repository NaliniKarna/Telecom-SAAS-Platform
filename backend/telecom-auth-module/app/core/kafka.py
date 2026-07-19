"""Platform Kafka infrastructure (reusable by all async modules).

This module is the ONLY place that touches aiokafka directly. Every future
module (Voice Campaigns, AI Broadcasting, Notifications, Scheduled Jobs) uses
the same producer/consumer classes — no Kafka boilerplate in business code.

Components:
  KafkaTopics       — Centralised topic registry (add new topics here only).
  PlatformProducer  — Async singleton producer. Call `produce(topic, key, value)`.
  PlatformConsumer  — Base consumer class. Subclass, implement `handle()`.
  DLQHandler        — Dead-letter-queue publisher for failed messages.
  kafka_lifespan()  — FastAPI lifespan hook (start/stop producer).

Idempotency:
  Every message carries a `message_id` (UUID v4) set by the producer. Consumers
  use an in-memory LRU set (and optionally a DB table) to skip duplicates.

Retry:
  PlatformConsumer retries `handle()` up to MAX_RETRIES with exponential backoff.
  After exhaustion the message is published to the topic's DLQ.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Topic registry ────────────────────────────────────────────────────────────
# Add new topics here. Workers and producers import this — never hardcode strings.

class KafkaTopics:
    """Canonical topic names. Extend for new modules."""
    # SMS Campaign pipeline
    SMS_CAMPAIGN_CREATED = "sms.campaign.created"
    SMS_MESSAGE_SEND = "sms.message.send"
    SMS_MESSAGE_STATUS = "sms.message.status.updated"

    # Dead letter queues (convention: topic + ".dlq")
    SMS_CAMPAIGN_CREATED_DLQ = "sms.campaign.created.dlq"
    SMS_MESSAGE_SEND_DLQ = "sms.message.send.dlq"
    SMS_MESSAGE_STATUS_DLQ = "sms.message.status.updated.dlq"

    # Future modules (reserved, not implemented yet)
    # VOICE_CAMPAIGN_CREATED = "voice.campaign.created"
    # NOTIFICATION_SEND = "notification.send"
    # SCHEDULED_JOB_TICK = "scheduled.job.tick"

    @classmethod
    def dlq_for(cls, topic: str) -> str:
        return f"{topic}.dlq"

    @classmethod
    def all_topics(cls) -> list[str]:
        return [
            v for k, v in vars(cls).items()
            if isinstance(v, str) and not k.startswith("_") and k.isupper()
        ]


# ── Message envelope ──────────────────────────────────────────────────────────

@dataclass
class KafkaMessage:
    """Standard envelope for all platform Kafka messages."""
    topic: str
    key: str                          # partition key (company_id or entity_id)
    payload: dict[str, Any]
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retries: int = 0

    def to_bytes(self) -> bytes:
        return json.dumps({
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "retries": self.retries,
            "payload": self.payload,
        }, default=str).encode("utf-8")

    @classmethod
    def from_bytes(cls, topic: str, key: bytes | None, value: bytes) -> "KafkaMessage":
        data = json.loads(value.decode("utf-8"))
        return cls(
            topic=topic,
            key=(key.decode("utf-8") if key else ""),
            payload=data.get("payload", data),
            message_id=data.get("message_id", uuid.uuid4().hex),
            timestamp=data.get("timestamp", ""),
            retries=data.get("retries", 0),
        )


# ── Producer ──────────────────────────────────────────────────────────────────

class PlatformProducer:
    """Async Kafka producer singleton.

    Usage:
        producer = PlatformProducer(bootstrap_servers="localhost:9092")
        await producer.start()
        await producer.produce("sms.campaign.created", key=company_id, value={...})
        await producer.stop()
    """

    def __init__(self, bootstrap_servers: str, client_id: str = "telecom-platform"):
        self._servers = bootstrap_servers
        self._client_id = client_id
        self._producer = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._servers,
                client_id=self._client_id,
                value_serializer=None,  # we serialize ourselves
                key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
                acks="all",             # durability: wait for all ISR replicas
                enable_idempotence=True, # exactly-once producer semantics
                max_request_size=1048576,
            )
            await self._producer.start()
            logger.info("Kafka producer started [%s]", self._servers)
        except ImportError:
            logger.warning("aiokafka not installed — Kafka producer disabled (NullProducer mode)")
            self._producer = None
        except Exception as exc:
            logger.error("Kafka producer failed to start: %s", exc)
            self._producer = None

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def produce(
        self, topic: str, *, key: str, value: dict[str, Any],
        message_id: str | None = None,
    ) -> str:
        """Publish a message. Returns the message_id."""
        msg = KafkaMessage(
            topic=topic, key=key, payload=value,
            message_id=message_id or uuid.uuid4().hex,
        )
        if self._producer is None:
            # NullProducer: log and return (for dev without Kafka)
            logger.info(
                "[NullProducer] topic=%s key=%s message_id=%s",
                topic, key, msg.message_id,
            )
            return msg.message_id

        await self._producer.send_and_wait(
            topic, value=msg.to_bytes(), key=key,
        )
        logger.info(
            "Produced message_id=%s topic=%s key=%s",
            msg.message_id, topic, key,
        )
        return msg.message_id

    @property
    def is_connected(self) -> bool:
        return self._producer is not None


# ── Consumer base ─────────────────────────────────────────────────────────────

class PlatformConsumer:
    """Base Kafka consumer. Subclass and implement `handle()`.

    Features:
      - Automatic deserialization into KafkaMessage
      - Idempotent: skips messages already processed (LRU set)
      - Retry with exponential backoff (configurable)
      - Dead-letter queue on exhaustion
      - Graceful shutdown via stop()
    """

    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2.0  # seconds; actual = base ** attempt
    DEDUP_CACHE_SIZE = 10_000

    def __init__(
        self,
        bootstrap_servers: str,
        topics: list[str],
        group_id: str,
        producer: PlatformProducer | None = None,
    ):
        self._servers = bootstrap_servers
        self._topics = topics
        self._group_id = group_id
        self._producer = producer  # for DLQ publishing
        self._running = False
        self._seen: OrderedDict[str, None] = OrderedDict()

    async def handle(self, message: KafkaMessage) -> None:
        """Process one message. Override in subclass.
        Raise to trigger retry; return to acknowledge."""
        raise NotImplementedError

    async def run(self) -> None:
        """Main consumer loop. Blocks until stop() is called."""
        try:
            from aiokafka import AIOKafkaConsumer
            from aiokafka.errors import CommitFailedError, UnknownMemberIdError
        except ImportError:
            logger.error("aiokafka not installed — cannot start consumer")
            return

        consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=self._servers,
            group_id=self._group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=None,
            # How long Kafka waits between poll() calls before assuming this
            # consumer is dead and kicking it out of the group. Processing
            # (DB writes, per-recipient Kafka publishes, retry backoff) can
            # legitimately take longer than the 5-minute default under load
            # or when the broker itself is flaky — raise this generously so
            # a slow campaign doesn't get the worker evicted mid-processing.
            max_poll_interval_ms=600_000,  # 10 minutes
            # Heartbeats are sent on a separate connection while poll() is
            # busy, so a long-running handle() doesn't need session_timeout
            # raised as aggressively — but give it some headroom too.
            session_timeout_ms=30_000,
        )
        await consumer.start()
        self._running = True
        logger.info(
            "Consumer started [group=%s topics=%s]", self._group_id, self._topics,
        )

        async def _safe_commit() -> bool:
            """Commit offsets, tolerating a rebalance that already evicted us.

            Returns True if committed, False if the group moved on without us
            (we simply resume consuming under the new assignment — no crash).
            """
            try:
                await consumer.commit()
                return True
            except (CommitFailedError, UnknownMemberIdError) as exc:
                logger.warning(
                    "Commit skipped — consumer group already rebalanced "
                    "(this message may be reprocessed by another member): %s",
                    exc,
                )
                return False

        try:
            async for record in consumer:
                if not self._running:
                    break
                try:
                    msg = KafkaMessage.from_bytes(
                        record.topic, record.key, record.value,
                    )

                    # Idempotency: skip duplicates
                    if msg.message_id in self._seen:
                        logger.debug("Skipping duplicate message_id=%s", msg.message_id)
                        await _safe_commit()
                        continue

                    # Process with retry
                    await self._process_with_retry(msg)

                    # Mark as seen
                    self._seen[msg.message_id] = None
                    if len(self._seen) > self.DEDUP_CACHE_SIZE:
                        self._seen.popitem(last=False)

                    await _safe_commit()

                except (CommitFailedError, UnknownMemberIdError):
                    # Belt-and-suspenders: even if this slips past _safe_commit
                    # (e.g. raised from a nested call), never let a rebalance
                    # race kill the whole worker process.
                    logger.warning(
                        "Rebalance-related commit error caught at message level — "
                        "continuing consumption under new assignment.",
                    )
                    continue
                except Exception as exc:
                    logger.exception(
                        "Unrecoverable error processing message: %s", exc,
                    )
                    await _safe_commit()  # don't get stuck; never crash on this
        finally:
            await consumer.stop()
            logger.info("Consumer stopped [group=%s]", self._group_id)

    async def _process_with_retry(self, msg: KafkaMessage) -> None:
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                await self.handle(msg)
                return
            except Exception as exc:
                if attempt < self.MAX_RETRIES:
                    wait = self.RETRY_BACKOFF_BASE ** attempt
                    logger.warning(
                        "Retry %d/%d for message_id=%s: %s (backoff %.1fs)",
                        attempt + 1, self.MAX_RETRIES, msg.message_id, exc, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "Exhausted retries for message_id=%s, sending to DLQ",
                        msg.message_id,
                    )
                    await self._send_to_dlq(msg, str(exc))

    async def _send_to_dlq(self, msg: KafkaMessage, error: str) -> None:
        if self._producer is None:
            logger.error("No producer for DLQ — message_id=%s lost", msg.message_id)
            return
        dlq_topic = KafkaTopics.dlq_for(msg.topic)
        dlq_payload = {
            **msg.payload,
            "_dlq_error": error,
            "_dlq_original_topic": msg.topic,
            "_dlq_retries": msg.retries + self.MAX_RETRIES,
        }
        await self._producer.produce(
            dlq_topic, key=msg.key, value=dlq_payload, message_id=msg.message_id,
        )

    async def stop(self) -> None:
        self._running = False


# ── Singleton holder (attached to app state via lifespan) ─────────────────────

_producer_instance: PlatformProducer | None = None
_producer_lock = asyncio.Lock()


async def get_producer() -> PlatformProducer:
    """Get the singleton producer, auto-starting it on first use.

    Safe to call even if the app's lifespan hook never explicitly started
    the producer. Lazily creates AND starts it exactly once, guarded by a
    lock against concurrent requests racing to initialize it.
    """
    global _producer_instance
    if _producer_instance is None:
        async with _producer_lock:
            if _producer_instance is None:  # re-check after acquiring lock
                from app.core.config import settings
                producer = PlatformProducer(settings.KAFKA_BOOTSTRAP_SERVERS)
                await producer.start()
                _producer_instance = producer
                logger.info("Kafka producer lazily initialized on first use")
    return _producer_instance


@asynccontextmanager
async def kafka_lifespan(bootstrap_servers: str):
    """FastAPI lifespan hook. Attach to your app:

        @asynccontextmanager
        async def lifespan(app):
            async with kafka_lifespan(settings.KAFKA_BOOTSTRAP_SERVERS):
                yield
    """
    global _producer_instance
    _producer_instance = PlatformProducer(bootstrap_servers)
    await _producer_instance.start()
    try:
        yield _producer_instance
    finally:
        await _producer_instance.stop()
        _producer_instance = None