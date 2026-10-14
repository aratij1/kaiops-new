import json
import urllib.request
import urllib.error
import time

url = "http://localhost:65028/resolve?publish_events=true"
headers = {"Content-Type": "application/json"}

with open("latest_context.json", "r", encoding="utf-8") as f:
    payload = json.load(f)

print(f"Loaded latest_context.json (size: {len(json.dumps(payload))} bytes)")
print(f"Incident ID: {payload.get('incident_id')}")
print(f"Alert ID: {payload.get('alert', {}).get('id')}")

req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

start = time.time()
print(f"Invoking {url} ...")
try:
    with urllib.request.urlopen(req, timeout=300) as resp:
        elapsed = time.time() - start
        body = resp.read().decode("utf-8")
        print(f"Success! Status: {resp.status} (Elapsed: {elapsed:.2f}s)")
        res = json.loads(body)
        print("Recommendation ID:", res.get("id"))
        print("Root Cause:", res.get("root_cause"))
        print("Confidence:", res.get("confidence"))
        print("Impact:", res.get("impact"))
        print("Recommended Action:", res.get("recommended_action"))
        metadata = res.get("metadata", {})
        print("RCA Status:", metadata.get("rca_status"))
        print("RCA Conclusive:", metadata.get("rca_conclusive"))
        print("Investigation Outcome:", metadata.get("investigation_outcome"))
        plan = metadata.get("execution_plan", {})
        print("Execution Plan ID:", plan.get("plan_id"))
        print("Plan Fingerprint:", plan.get("plan_fingerprint"))
        print("Plan Execution Ready:", plan.get("execution_ready"))
        print("Plan Requires Approval:", plan.get("requires_approval"))
        print("Plan Readiness Blocks:", plan.get("readiness_blocks"))
        with open("scratch/last_resolve_response.json", "w", encoding="utf-8") as out:
            json.dump(res, out, indent=2)
except urllib.error.HTTPError as err:
    elapsed = time.time() - start
    print(f"HTTP Error {err.code}: {err.reason} (Elapsed: {elapsed:.2f}s)")
    err_body = err.read().decode("utf-8")
    print("Error body:", err_body)
except Exception as e:
    elapsed = time.time() - start
    print(f"Unexpected error: {e} (Elapsed: {elapsed:.2f}s)")
