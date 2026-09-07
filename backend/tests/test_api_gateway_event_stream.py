import asyncio
from types import SimpleNamespace

import anyio
import pytest
from test_api_gateway_safety import load_api_gateway_app_module
from common.resilience import CircuitOpenError


@pytest.mark.asyncio
async def test_disconnect_during_poll_returns_session_before_cancellation(monkeypatch):
    module = load_api_gateway_app_module()
    closed = []
    statements = []
    scope = anyio.CancelScope()

    class Session:
        async def __aenter__(self):
            return self

        async def execute(self, statement):
            statements.append(str(statement))
            scope.cancel()  # The outer Starlette request scope was disconnected.
            await anyio.sleep(0)
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

        async def __aexit__(self, *args):
            await anyio.sleep(0)
            closed.append(True)

    monkeypatch.setattr(module.settings, "database_enabled", True)
    monkeypatch.setattr(module.app.state, "session_factory", Session, raising=False)

    async def connected():
        return False

    request = SimpleNamespace(state=SimpleNamespace(), headers={}, query_params={}, is_disconnected=connected)
    response = await module.stream_operational_events(request)
    iterator = response.body_iterator
    await anext(iterator)
    with scope:
        await anext(iterator)
        await anyio.sleep(0)
    await iterator.aclose()
    assert closed == [True]
    assert len(statements) == 4
    assert all("payload" not in statement for statement in statements)


@pytest.mark.asyncio
@pytest.mark.parametrize("stalled", [False, True])
async def test_database_outage_after_headers_closes_stream_cleanly(monkeypatch, stalled):
    module = load_api_gateway_app_module()
    closed = []
    native_timeout = asyncio.timeout
    monkeypatch.setattr(module.asyncio, "timeout", lambda seconds: native_timeout(0.01))

    class Session:
        async def __aenter__(self):
            return self

        async def execute(self, statement):
            if stalled:
                await asyncio.sleep(60)
            raise CircuitOpenError("database unavailable")

        async def __aexit__(self, *args):
            closed.append(True)

    async def connected():
        return False

    monkeypatch.setattr(module.settings, "database_enabled", True)
    monkeypatch.setattr(module.app.state, "session_factory", Session, raising=False)
    request = SimpleNamespace(state=SimpleNamespace(), headers={}, query_params={}, is_disconnected=connected)
    response = await module.stream_operational_events(request)
    events = [event async for event in response.body_iterator]
    assert len(events) == 2
    assert "dependency.unavailable" in events[-1]
    assert closed == [True]
