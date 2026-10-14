from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from sqlalchemy import text

logger = logging.getLogger("common.advisory_lock")


@asynccontextmanager
async def advisory_session(session_factory: Any, lock_name: str, timeout: int = 0, wait_seconds: int | None = None) -> AsyncIterator[Any]:
    effective_timeout = timeout if wait_seconds is None else wait_seconds
    async with session_factory() as session:
        acquired = await session.scalar(text(f"SELECT GET_LOCK('{lock_name}', {effective_timeout})"))
        if int(acquired or 0) != 1:
            yield None
            return
        try:
            yield session
        finally:
            try:
                await session.execute(text(f"SELECT RELEASE_LOCK('{lock_name}')"))
                await session.commit()
            except Exception:
                # A lock that could not be released stays attached to the pooled
                # connection and blocks every later caller. Drop the connection.
                try:
                    await session.invalidate()
                except Exception:
                    pass


@asynccontextmanager
async def advisory_connection(engine: Any, lock_name: str, wait_seconds: int = 0) -> AsyncIterator[Any]:
    async with engine.connect() as connection:
        acquired = await connection.scalar(text(f"SELECT GET_LOCK('{lock_name}', {wait_seconds})"))
        if int(acquired or 0) != 1:
            yield None
            return
        try:
            yield connection
        finally:
            try:
                await connection.execute(text(f"SELECT RELEASE_LOCK('{lock_name}')"))
                await connection.commit()
            except Exception:
                pass
