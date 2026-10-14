from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Sequence

logger = logging.getLogger("common.enrichment_scheduler")


class CollectionPersistenceBusy(Exception):
    pass


def transient_collection_database_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "deadlock" in msg or "lock wait timeout" in msg or "busy" in msg


async def persist_collected_evidence(session_factory: Any, persist_fn: Callable[[Any], Coroutine[Any, Any, Any]]) -> Any:
    async with session_factory() as session:
        try:
            result = await persist_fn(session)
            # Without this commit the session closes and rolls back: the worker logs
            # "persisted" but the job stays in `collecting` and is re-collected forever.
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def run_leased_collection_batch(
    jobs: Sequence[Any],
    process_job: Callable[[Any], Coroutine[Any, Any, None]],
    on_collection_timeout: Callable[[Any], Coroutine[Any, Any, None]] | None = None,
    timeout_seconds: float = 110.0,
) -> None:
    async def _run_single(job: Any) -> None:
        try:
            await asyncio.wait_for(process_job(job), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            if on_collection_timeout:
                try:
                    await on_collection_timeout(job)
                except Exception:
                    logger.exception("enrichment collection timeout handler failed")
        except Exception:
            logger.exception("enrichment job execution failed")

    await asyncio.gather(*[_run_single(job) for job in jobs], return_exceptions=True)
