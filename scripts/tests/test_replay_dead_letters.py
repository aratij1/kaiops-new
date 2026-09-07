import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
spec=importlib.util.spec_from_file_location("replay",Path(__file__).parents[1]/"replay_dead_letters.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
@pytest.mark.asyncio
async def test_acknowledges_only_after_confirmed_publication():
 events=[]
 async def publish(*args,**kwargs): events.append("publish");return True
 async def ack():events.append("ack")
 message=SimpleNamespace(body=b'{"failed_topic":"context-events","payload":{"id":"x"}}',ack=ack,reject=AsyncMock())
 assert await module.replay_confirmed_message(message,SimpleNamespace(publish=publish))
 assert events==["publish","ack"]
@pytest.mark.asyncio
async def test_failed_publish_keeps_original_delivery():
 message=SimpleNamespace(body=b'{"failed_topic":"context-events","payload":{}}',ack=AsyncMock(),reject=AsyncMock())
 with pytest.raises(RuntimeError): await module.replay_confirmed_message(message,SimpleNamespace(publish=AsyncMock(side_effect=RuntimeError("unroutable"))))
 message.ack.assert_not_called();message.reject.assert_awaited_once_with(requeue=True)
@pytest.mark.asyncio
async def test_malformed_envelope_is_not_removed():
 message=SimpleNamespace(body=b'{}',ack=AsyncMock(),reject=AsyncMock())
 assert not await module.replay_confirmed_message(message,SimpleNamespace(publish=AsyncMock()))
 message.ack.assert_not_called();message.reject.assert_awaited_once_with(requeue=True)
