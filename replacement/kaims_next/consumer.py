"""Bounded stage execution with confirmed retry/quarantine transfers before ACK."""
import asyncio
import json


class StageConsumer:
    def __init__(self, worker, retry_confirmed, quarantine_confirmed, *, timeout=30, max_attempts=3):
        if timeout<=0 or max_attempts<1: raise ValueError("Invalid retry policy")
        self.worker,self.retry,self.quarantine=worker,retry_confirmed,quarantine_confirmed
        self.timeout,self.max_attempts=timeout,max_attempts

    async def handle(self, message):
        envelope=None
        try:
            if len(message.body)>16384: raise ValueError("oversized_event")
            envelope=json.loads(message.body)
            if not isinstance(envelope,dict) or envelope.get("topic")!=message.routing_key:
                raise ValueError("invalid_routing")
            attempts=int((message.headers or {}).get("kaims-attempt",1))
            if attempts<1: raise ValueError("invalid_attempt")
            await asyncio.wait_for(self.worker.handle(envelope),self.timeout)
        except (ValueError,KeyError,TypeError) as error:
            # Malformed events cannot identify a trustworthy application to mutate.
            # Quarantine preserves the original message for an operator to inspect.
            await self.quarantine(message,type(error).__name__)
        except Exception as error:
            attempts=int((message.headers or {}).get("kaims-attempt",1))
            if attempts<self.max_attempts:
                await self.retry(message,attempts+1)
            else:
                # Persist terminal state/outbox before handing off the failed delivery.
                await self.worker.fail(envelope,type(error).__name__)
                await self.quarantine(message,type(error).__name__)
        # If a transfer or persistence failed, propagate without acknowledging.
        await message.ack()
