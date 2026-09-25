from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("common.queue_backpressure")


def controller_enabled(enabled: bool, provider: str, is_connected: bool) -> bool:
    return bool(enabled and provider == "rabbitmq" and is_connected)


async def backlog_loop(settings: Any) -> None:
    logger.info("queue backlog controller loop started")
    while True:
        await asyncio.sleep(60)
