from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from urllib.parse import unquote, urlparse

try:
    import aio_pika
except ImportError:
    aio_pika = None

from common.message_processing import extract_processing_identities

logger = logging.getLogger("common.queue_management")


def broker_vhost(url: str) -> str:
    """Parse and decode the RabbitMQ virtual host from an AMQP URL."""
    parsed = urlparse(url)
    path = parsed.path
    if not path or path == "/":
        return "/"
    trimmed = path[1:]
    decoded = unquote(trimmed)
    if decoded == "" or decoded == "/":
        return "/"
    return decoded


def queue_job_id(queue_name: str, payload: bytes) -> str:
    """Generate a deterministic job identifier scoped to a queue and message payload."""
    hasher = hashlib.sha256()
    hasher.update(queue_name.encode("utf-8"))
    hasher.update(b":")
    hasher.update(payload)
    return f"job-{hasher.hexdigest()[:24]}"


def describe_message(queue_name: str, body: bytes) -> dict[str, Any]:
    """Inspect a raw message payload and extract metadata and workflow identities."""
    jid = queue_job_id(queue_name, body)
    row: dict[str, Any] = {
        "job_id": jid,
        "queue_name": queue_name,
        "payload_bytes": len(body),
        "payload_valid": False,
        "name": "Queued event",
        "alert_id": None,
        "incident_id": None,
        "identities": [],
    }

    try:
        parsed = json.loads(body.decode("utf-8"))
        if isinstance(parsed, dict):
            row["payload_valid"] = True
            row["name"] = str(parsed.get("name") or parsed.get("event_type") or "Queued event")
            identities = extract_processing_identities(parsed)
            row["identities"] = identities

            # Check direct or nested alert/incident ids
            alert_id = (
                parsed.get("alert_id")
                or (parsed.get("alert") if isinstance(parsed.get("alert"), dict) else {}).get("id")
                or (parsed.get("context") if isinstance(parsed.get("context"), dict) else {}).get("alert_id")
            )
            incident_id = (
                parsed.get("incident_id")
                or (parsed.get("incident") if isinstance(parsed.get("incident"), dict) else {}).get("id")
                or (parsed.get("context") if isinstance(parsed.get("context"), dict) else {}).get("incident_id")
            )
            if alert_id:
                row["alert_id"] = str(alert_id)
            if incident_id:
                row["incident_id"] = str(incident_id)
    except Exception:
        row["payload_valid"] = False

    return row


async def sample_ready_messages(
    broker_url: str,
    queue_name: str,
    max_messages: int = 100,
) -> list[dict[str, Any]]:
    """Sample up to max_messages ready messages from a queue and requeue them safely."""
    if aio_pika is None:
        return []

    connection = await aio_pika.connect_robust(broker_url)
    sampled: list[dict[str, Any]] = []
    try:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(queue_name, passive=True)

        for _ in range(max_messages):
            message = await queue.get(no_ack=False, fail=False)
            if message is None:
                break
            try:
                row = describe_message(queue_name, message.body)
                sampled.append(row)
            finally:
                await message.reject(requeue=True)
    finally:
        await connection.close()

    return sampled


async def mutate_ready_queue_job(
    broker_url: str,
    queue_name: str,
    job_id: str,
    rerun: bool = False,
    delete: bool = False,
) -> bool:
    """Find a ready queue message by job ID to either republish (rerun) or discard (delete)."""
    if aio_pika is None:
        return False

    connection = await aio_pika.connect_robust(broker_url)
    matched = False
    try:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(queue_name, passive=True)

        requeue_messages = []
        while True:
            message = await queue.get(no_ack=False, fail=False)
            if message is None:
                break
            current_id = queue_job_id(queue_name, message.body)
            if current_id == job_id:
                matched = True
                if rerun:
                    # Publish new message copy first, only ack once publish succeeds
                    new_msg = aio_pika.Message(
                        body=message.body,
                        headers=dict(message.headers or {}),
                        content_type=message.content_type,
                        content_encoding=message.content_encoding,
                        correlation_id=message.correlation_id,
                        message_id=message.message_id,
                        timestamp=message.timestamp,
                        type=message.type,
                        app_id=message.app_id,
                    )
                    await channel.default_exchange.publish(
                        new_msg,
                        routing_key=queue_name,
                    )
                    await message.ack()
                elif delete:
                    await message.ack()
                else:
                    await message.reject(requeue=True)
                break
            else:
                requeue_messages.append(message)

        # Requeue any messages we inspected but didn't mutate
        for msg in requeue_messages:
            await msg.reject(requeue=True)
    finally:
        await connection.close()

    return matched
