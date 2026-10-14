import sys
sys.path.insert(0, "backend/src/common")
sys.path.insert(0, "ai-workbench/src/resolution-agent")

import asyncio
from common.database import create_session_factory
from common.repository import IncidentRepository

async def test():
    factory = get_session_factory()
    async with factory() as session:
        repo = IncidentRepository(session)
        incident_id = "9a7aac0b-0fd8-423a-bc10-36ddf40e8dad"
        tenant_id = "default"
        inc = await repo.get_incident(incident_id, tenant_id=tenant_id)
        print("Incident:", inc.get("id") if inc else None, inc.get("status") if inc else None)
        rec = await repo.get_latest_recommendation_for_incident(incident_id, tenant_id=tenant_id)
        print("Recommendation:", rec.get("id") if rec else None)
        if rec:
            print("Rec metadata keys:", list(rec.get("metadata", {}).keys()))
            rca_ver = int(rec.get("metadata", {}).get("rca_version") or 1)
            print("rca_version:", rca_ver)
            plan = await repo.get_current_execution_plan_for_incident(
                tenant_id=tenant_id,
                incident_id=incident_id,
                recommendation_id=rec.get("id"),
                rca_version=rca_ver
            )
            print("Plan loaded:", bool(plan))
            if plan:
                print("Plan ID:", plan.get("plan_id"))
                print("Plan fingerprint:", plan.get("plan_fingerprint"))
                print("Plan execution ready:", plan.get("execution_ready"))
                print("Plan tenant_id:", plan.get("tenant_id"))
                print("Plan incident_id:", plan.get("incident_id"))
                print("Policy version:", plan.get("policy_version"))
                print("Evidence snapshot id:", plan.get("evidence_snapshot_id"))
                print("Context fingerprint:", plan.get("context_fingerprint"))
                print("Resolution selection id:", plan.get("resolution_selection_id"))

asyncio.run(test())
