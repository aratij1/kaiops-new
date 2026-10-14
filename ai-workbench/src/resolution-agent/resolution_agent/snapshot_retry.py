from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _is_snapshot_conflict(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if any(term in msg for term in ("superseded", "snapshot", "stale", "expired", "conflict")):
        return True
    if getattr(exc, "status_code", None) == 409:
        return True
    return False


async def run_with_snapshot_refresh(
    payload: Any,
    attempt_fn: Callable[[Any], Coroutine[Any, Any, T]],
    refresh_fn: Callable[[Any], Coroutine[Any, Any, Any | None]],
    max_attempts: int = 3,
) -> T:
    """Execute attempt_fn with snapshot refresh retry semantics.

    If an attempt fails due to a superseded or stale snapshot conflict,
    fetch the latest snapshot via refresh_fn and retry up to max_attempts.
    """
    current_payload = payload
    for attempt in range(max_attempts):
        try:
            return await attempt_fn(current_payload)
        except Exception as exc:
            if attempt >= max_attempts - 1:
                raise
            if _is_snapshot_conflict(exc):
                try:
                    refreshed = await refresh_fn(current_payload)
                except Exception as refresh_err:
                    logger.warning("failed to refresh context snapshot: %s", refresh_err)
                    raise exc from refresh_err

                if refreshed is not None:
                    logger.info(
                        "snapshot conflict encountered (attempt %d/%d), retrying with latest snapshot: %s",
                        attempt + 1,
                        max_attempts,
                        exc,
                    )
                    current_payload = refreshed
                    await asyncio.sleep(0.5)
                    continue
            raise
    return await attempt_fn(current_payload)
