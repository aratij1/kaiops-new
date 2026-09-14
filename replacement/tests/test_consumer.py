import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from kaims_next.consumer import StageConsumer


class Message:
    routing_key="application.discovery.requested"
    def __init__(self,attempt=1):
        self.body=json.dumps({"topic":self.routing_key}).encode()
        self.headers={"kaims-attempt":attempt}
        self.ack=AsyncMock()


@pytest.mark.asyncio
async def test_success_acknowledges_after_handler_commit():
    message=Message();worker=AsyncMock()
    async def handle(_): message.ack.assert_not_awaited()
    worker.handle.side_effect=handle
    await StageConsumer(worker,AsyncMock(),AsyncMock()).handle(message)
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_transfer_failure_leaves_original_unacknowledged():
    message=Message();worker=AsyncMock();worker.handle.side_effect=OSError()
    retry=AsyncMock(side_effect=ConnectionError())
    with pytest.raises(ConnectionError): await StageConsumer(worker,retry,AsyncMock()).handle(message)
    message.ack.assert_not_awaited()
    worker.fail.assert_not_awaited()


@pytest.mark.asyncio
async def test_exhausted_attempt_persists_terminal_failure_before_quarantine():
    message=Message(3);worker=AsyncMock();worker.handle.side_effect=TimeoutError()
    dead=AsyncMock()
    async def quarantine(*_):
        worker.fail.assert_awaited_once()
        message.ack.assert_not_awaited()
    dead.side_effect=quarantine
    await StageConsumer(worker,AsyncMock(),dead).handle(message)
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_malformed_delivery_is_quarantined_without_business_state_changes():
    message=Message();message.body=b'not json';worker=AsyncMock();dead=AsyncMock()
    await StageConsumer(worker,AsyncMock(),dead).handle(message)
    worker.handle.assert_not_awaited();worker.fail.assert_not_awaited()
    dead.assert_awaited_once();message.ack.assert_awaited_once()
