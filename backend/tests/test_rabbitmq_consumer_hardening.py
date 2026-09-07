"""RabbitMQConsumer previously never bounded prefetch (a channel drop mid-backlog
could leave thousands of delivered-but-unacked messages that all fail to nack
together) and consume_forever never bounded a single handler's runtime (a hung
downstream call could block a consumer indefinitely). Both are now bounded and
configurable.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from common.config import Settings
from common.rabbitmq import RabbitMQConsumer, _is_transient_handler_error, consume_forever


def test_transient_dependency_errors_are_requeueable() -> None:
    assert _is_transient_handler_error("Can't connect to MySQL server on 'mysql'")
    assert _is_transient_handler_error("Temporary failure in name resolution")
    assert _is_transient_handler_error("request timed out")
    assert not _is_transient_handler_error("context field is required")


class _FakeQueue:
    def __init__(self, name: str) -> None:
        self.name = name
        self.bind_calls: list[tuple[object, str]] = []

    async def bind(self, exchange: object, routing_key: str) -> None:
        self.bind_calls.append((exchange, routing_key))


class _FakeChannel:
    def __init__(self) -> None:
        self.qos_calls: list[int] = []
        self.declared_queues: list[_FakeQueue] = []

    async def set_qos(self, prefetch_count: int) -> None:
        self.qos_calls.append(prefetch_count)

    async def declare_exchange(self, _name: str, _exchange_type, durable: bool = True) -> object:
        return object()

    async def declare_queue(self, name: str, durable: bool = True) -> _FakeQueue:
        queue = _FakeQueue(name)
        self.declared_queues.append(queue)
        return queue


class _FakeConnection:
    def __init__(self) -> None:
        self.channel_obj = _FakeChannel()

    async def channel(self) -> _FakeChannel:
        return self.channel_obj

    async def close(self) -> None:
        return None


@pytest.fixture
def fake_connection(monkeypatch: pytest.MonkeyPatch) -> _FakeConnection:
    connection = _FakeConnection()

    async def fake_connect_robust(_url: str) -> _FakeConnection:
        return connection

    monkeypatch.setattr("common.rabbitmq.aio_pika.connect_robust", fake_connect_robust)
    return connection


async def test_start_sets_configured_prefetch(fake_connection: _FakeConnection) -> None:
    settings = Settings(RABBITMQ_CONSUMER_PREFETCH_COUNT=7)
    consumer = RabbitMQConsumer(settings, "raw-alerts")

    await consumer.start()

    assert fake_connection.channel_obj.qos_calls == [7]


async def test_start_defaults_prefetch_to_ten(fake_connection: _FakeConnection) -> None:
    consumer = RabbitMQConsumer(Settings(), "raw-alerts")

    await consumer.start()

    assert fake_connection.channel_obj.qos_calls == [10]


class _FakeMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = 0
        self.nacked: list[bool] = []

    async def ack(self) -> None:
        self.acked += 1

    async def nack(self, requeue: bool = True) -> None:
        self.nacked.append(requeue)


class _FakeIterator:
    """Yields queued messages once, then parks forever (simulating an idle
    queue) so the test can cancel the consumer task deterministically instead
    of racing a fixed sleep."""

    def __init__(self, messages: list[_FakeMessage], parked: asyncio.Event) -> None:
        self._messages = messages
        self._parked = parked

    def __aiter__(self) -> "_FakeIterator":
        return self

    async def __anext__(self) -> _FakeMessage:
        if self._messages:
            return self._messages.pop(0)
        await self._parked.wait()
        raise StopAsyncIteration


class _FakeIteratorCtx:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._messages = messages
        self.parked = asyncio.Event()

    def __call__(self) -> "_FakeIteratorCtx":
        return self

    async def __aenter__(self) -> _FakeIterator:
        return _FakeIterator(self._messages, self.parked)

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeConsumerQueue:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._ctx = _FakeIteratorCtx(messages)

    def iterator(self) -> _FakeIteratorCtx:
        return self._ctx


async def test_hung_handler_times_out_and_nacks_instead_of_blocking_forever() -> None:
    settings = Settings(RABBITMQ_HANDLER_TIMEOUT_SECONDS=0.05, RABBITMQ_CONSUMER_MAX_RETRIES=0)
    consumer = RabbitMQConsumer(settings, "raw-alerts")
    consumer._connection = object()  # bypass real start(): already "connected"
    consumer._exchange = None
    consumer._dlq_routing_key = None

    message = _FakeMessage(json.dumps({"payload": {"id": "evt-1"}}).encode("utf-8"))
    consumer._queue = _FakeConsumerQueue([message])

    async def hanging_handler(_payload: dict) -> None:
        await asyncio.sleep(10)  # far longer than the configured timeout

    task = asyncio.create_task(consume_forever(consumer, hanging_handler))
    try:
        for _ in range(200):
            if message.nacked:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("handler timeout never resulted in a nack")
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert message.nacked == [True]
    assert message.acked == 0


class _FakeExchange:
    def __init__(self) -> None:
        self.published: list[dict] = []

    async def publish(self, message: object, routing_key: str) -> None:
        self.published.append({"routing_key": routing_key, "body": json.loads(message.body)})


async def test_handler_failure_reaches_failure_handler_sanitized_but_dlq_keeps_raw_detail() -> None:
    """Reproduces the exact production leak: a redelivered event hit a real
    MySQL unique-constraint violation, and that raw exception text --
    "(raised as a result of Query-invoked autoflush ...) Duplicate entry
    'rabbitmq-incident.context.collected:...' for key
    'uq_incident_events_idempotency'" -- reached AnalysisRequestRecord.
    terminal_reason and was displayed to an operator verbatim. failure_handler
    must now receive a short, safe category instead; the DLQ envelope (an
    operator/internal surface, never displayed to an end user) keeps the raw
    detail so nothing useful for debugging is lost.
    """
    settings = Settings(RABBITMQ_HANDLER_TIMEOUT_SECONDS=1.0, RABBITMQ_CONSUMER_MAX_RETRIES=0)
    consumer = RabbitMQConsumer(settings, "orchestration-events")
    consumer._connection = object()
    consumer._exchange = _FakeExchange()
    consumer._dlq_routing_key = "orchestration-events.dlq"

    message = _FakeMessage(json.dumps({"payload": {"id": "evt-1"}}).encode("utf-8"))
    consumer._queue = _FakeConsumerQueue([message])

    raw_sql_error = (
        "(pymysql.err.IntegrityError) (1062, \"Duplicate entry "
        "'rabbitmq-incident.context.collected:8a3c3d3b' for key "
        "'uq_incident_events_idempotency'\") [SQL: INSERT INTO incident_events ...]"
    )

    async def failing_handler(_payload: dict) -> None:
        raise RuntimeError(raw_sql_error)

    received: list[tuple[dict, str]] = []

    async def failure_handler(payload: dict, error: str) -> None:
        received.append((payload, error))

    task = asyncio.create_task(consume_forever(consumer, failing_handler, failure_handler))
    try:
        for _ in range(200):
            if received:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("failure_handler was never invoked")
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    _, sanitized = received[0]
    assert sanitized == "A duplicate or conflicting record was detected; this was safely coalesced."
    assert "Duplicate entry" not in sanitized
    assert "pymysql" not in sanitized
    assert "uq_incident_events_idempotency" not in sanitized

    # The DLQ envelope is an operator/internal surface, not something an
    # end user's UI displays -- it must keep the full original detail.
    dlq_body = consumer._exchange.published[0]["body"]
    assert "uq_incident_events_idempotency" in dlq_body["error"]


def test_new_consumer_exposes_zero_deadletters_without_resetting_existing_count(monkeypatch):
    from prometheus_client import CollectorRegistry, Counter
    import common.rabbitmq as rabbitmq
    from common.config import Settings
    registry = CollectorRegistry()
    counter = Counter("test_deadletters", "Failures", ["provider", "queue", "reason"], registry=registry)
    monkeypatch.setattr(rabbitmq, "DEAD_LETTER_EVENTS", counter)
    rabbitmq.RabbitMQConsumer(Settings(), "context-events")
    labels = {"provider":"rabbitmq", "queue":"context-events", "reason":"handler_failed"}
    assert registry.get_sample_value("test_deadletters_total", labels) == 0
    counter.labels(**labels).inc(2)
    rabbitmq.RabbitMQConsumer(Settings(), "context-events")
    assert registry.get_sample_value("test_deadletters_total", labels) == 2
