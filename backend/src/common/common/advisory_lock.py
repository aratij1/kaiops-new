from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from sqlalchemy import text

logger = logging.getLogger("common.advisory_lock")


@asynccontextmanager
async def advisory_session(session_factory: Any, lock_name: str, timeout: int = 0) -> AsyncIterator[Any]:
    async with session_factory() as session:
        bind = getattr(session, "bind", None)
        dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "")).lower()
        is_sqlite = "sqlite" in dialect_name
        if is_sqlite:
            acquired = 1
        else:
            try:
                acquired = await session.scalar(text(f"SELECT GET_LOCK('{lock_name}', {timeout})"))
            except Exception:
                acquired = 1

        if int(acquired or 0) != 1:
            yield None
            return
        try:
            yield session
        finally:
            if not is_sqlite:
                try:
                    await session.execute(text(f"SELECT RELEASE_LOCK('{lock_name}')"))
                    await session.commit()
                except Exception:
                    pass


@asynccontextmanager
async def advisory_connection(engine: Any, lock_name: str, wait_seconds: int = 0) -> AsyncIterator[Any]:
    dialect_name = str(getattr(getattr(engine, "dialect", None), "name", "")).lower()
    is_sqlite = "sqlite" in dialect_name
    async with engine.connect() as connection:
        if is_sqlite:
            acquired = 1
        else:
            try:
                acquired = await connection.scalar(text(f"SELECT GET_LOCK('{lock_name}', {wait_seconds})"))
            except Exception:
                acquired = 1

        if int(acquired or 0) != 1:
            yield None
            return
        try:
            yield connection
        finally:
            if not is_sqlite:
                try:
                    await connection.execute(text(f"SELECT RELEASE_LOCK('{lock_name}')"))
                    await connection.commit()
                except Exception:
                    pass
