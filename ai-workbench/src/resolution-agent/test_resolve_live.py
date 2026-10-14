import json
import traceback
import asyncio
from httpx import AsyncClient, ASGITransport
from app import app

async def main():
    try:
        with open('/tmp/scratch_context.json') as f:
            ctx_data = json.load(f)
            
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Let's call /resolve!
            resp = await ac.post("/resolve?publish_events=false", json=ctx_data)
            print("Response status:", resp.status_code)
            if resp.status_code == 200:
                rec = resp.json()
                print("Rec conclusive (via outcome):", rec.get("metadata", {}).get("resolution_outcome"))
                print("Rec root_cause:", rec.get("root_cause"))
                print("Rec confidence:", rec.get("confidence"))
                print("Rec remediation_plan:", rec.get("remediation_plan"))
                exec_plan = rec.get("metadata", {}).get("execution_plan")
                if exec_plan:
                    print("Exec plan playbook_id:", exec_plan.get("playbook_id"))
                    print("Exec plan execution_ready:", exec_plan.get("execution_ready"))
                    print("Exec plan commands:", exec_plan.get("commands"))
                    print("Exec plan readiness_blocks:", exec_plan.get("readiness_blocks"))
                else:
                    print("Exec plan is NONE")
            else:
                print("Error:", resp.text)
    except Exception as e:
        traceback.print_exc()

asyncio.run(main())
