"""Onboarding workers; broker acknowledgment follows committed stage completion."""
import asyncio
import json
from datetime import datetime
from uuid import UUID

from .discovery import prepare_context


class OnboardingWorker:
    topics={"application.discovery.requested":"discovery", "application.context.requested":"context"}

    def __init__(self, store, discovery):
        self.store,self.discovery=store,discovery

    async def handle(self, envelope):
        if envelope.get("schema_version")!=1 or envelope.get("topic") not in self.topics:
            raise ValueError("Unsupported event schema or topic")
        UUID(envelope["event_id"])
        if datetime.fromisoformat(envelope["created_at"]).tzinfo is None:
            raise ValueError("Event timestamp requires timezone")
        consumer=self.topics[envelope["topic"]]
        if self.store.consumed(consumer,envelope["event_id"]): return False
        application=self.store.application(envelope["tenant_id"],envelope["application_id"])
        if consumer=="discovery":
            manifest=await asyncio.to_thread(self.discovery.collect,application["config"])
            return self.store.complete(consumer,envelope,expected_state="discovery_queued",next_state="context_queued",
                next_topic="application.context.requested",result=manifest)
        refs=envelope.get("artifact_refs",[])
        if len(refs)!=1: raise ValueError("Context requires exactly one discovery manifest")
        manifest=self.store.artifact(envelope["tenant_id"],envelope["application_id"],refs[0])
        baseline=prepare_context(manifest,refs[0])
        return self.store.complete(consumer,envelope,expected_state="context_queued",
            next_state="context_ready" if baseline["baseline_ready"] else "context_blocked",
            next_topic="application.context.ready" if baseline["baseline_ready"] else "application.context.blocked",result=baseline)

    async def fail(self, envelope, reason):
        consumer=self.topics[envelope["topic"]]
        if self.store.consumed(consumer,envelope["event_id"]): return False
        expected="discovery_queued" if consumer=="discovery" else "context_queued"
        return self.store.complete(consumer,envelope,expected_state=expected,next_state="context_blocked",
            next_topic="application.context.blocked",result={"reason":reason,"failed_stage":consumer,
                "baseline_ready":False,"incident_evidence_required":True})

    async def delivery(self, message):
        # Exceptions propagate to the bounded retry/quarantine transport layer.
        if len(message.body)>16384: raise ValueError("Oversized message")
        envelope=json.loads(message.body)
        if envelope.get("topic")!=message.routing_key: raise ValueError("Routing key mismatch")
        await self.handle(envelope)
        await message.ack()
