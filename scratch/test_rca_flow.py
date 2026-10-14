import json
import time
import urllib.request
import urllib.error

GATEWAY_URL = "http://localhost:62673"
INCIDENT_ID = "0d367082-ed9a-4b18-86dd-ad9826bbbcd9"

def req_json(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = err_body
        return e.code, parsed

def main():
    print(f"=== PART 5: RCA & AI VERIFICATION FOR INCIDENT {INCIDENT_ID} ===")
    
    # 1. Login
    code, auth = req_json(f"{GATEWAY_URL}/auth/login", method="POST", data={"username": "admin", "password": "Admin@123456"})
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Logged in successfully.")

    # 2. Check operations-state
    s_op, res_op = req_json(f"{GATEWAY_URL}/incidents/{INCIDENT_ID}/operations-state", headers=headers)
    print(f"\n1. Operations State (HTTP {s_op}):")
    if s_op == 200:
        inv = res_op.get("investigation_workspace", {})
        print(f"  - Title: {res_op.get('incident', {}).get('title')}")
        print(f"  - Status: {res_op.get('incident', {}).get('status')}")
        print(f"  - RCA Summary: {inv.get('rca', {}).get('summary') if inv.get('rca') else 'None'}")
        print(f"  - Root Cause: {inv.get('rca', {}).get('root_cause') if inv.get('rca') else 'None'}")
        print(f"  - Confidence: {inv.get('rca', {}).get('confidence') if inv.get('rca') else 'None'}")
        print(f"  - Hypotheses count: {len(inv.get('hypotheses', []))}")
        print(f"  - Evidence items: {len(inv.get('evidence', []))}")
        print(f"  - Timeline events: {len(res_op.get('timeline', []))}")

    # 3. Check command workspace
    s_cmd, res_cmd = req_json(f"{GATEWAY_URL}/incidents/{INCIDENT_ID}/command", headers=headers)
    print(f"\n2. Command Workspace (HTTP {s_cmd}):")
    if s_cmd == 200:
        ev = res_cmd.get("evidence", {})
        print(f"  - Evidence scores: {ev.get('scores')}")
        print(f"  - Summary fields: {list(res_cmd.get('summary', {}).keys()) if res_cmd.get('summary') else 'None'}")

    # 4. Trigger fresh investigation if RCA is not populated or test manual trigger
    print(f"\n3. Testing Trigger Fresh Investigation...")
    s_trig, res_trig = req_json(f"{GATEWAY_URL}/incidents/{INCIDENT_ID}/investigation/refresh", method="POST", data={}, headers=headers)
    print(f"  Trigger Investigation endpoint /investigation/refresh: HTTP {s_trig}, response: {res_trig}")
    if s_trig != 200:
        s_alt, res_alt = req_json(f"{GATEWAY_URL}/incidents/{INCIDENT_ID}/investigate", method="POST", data={}, headers=headers)
        print(f"  Alternative /investigate: HTTP {s_alt}, response: {res_alt}")

    # Wait for investigation
    time.sleep(5)

    # 5. Check operations-state again
    s_op2, res_op2 = req_json(f"{GATEWAY_URL}/incidents/{INCIDENT_ID}/operations-state", headers=headers)
    if s_op2 == 200:
        inv2 = res_op2.get("investigation_workspace", {})
        print(f"\n4. Post-investigation Operations State:")
        print(f"  - RCA: {json.dumps(inv2.get('rca'), indent=2) if inv2.get('rca') else 'None'}")
        print(f"  - Hypotheses: {json.dumps(inv2.get('hypotheses'), indent=2) if inv2.get('hypotheses') else 'None'}")
        print(f"  - Recommended actions: {json.dumps(inv2.get('recommendations'), indent=2) if inv2.get('recommendations') else 'None'}")

if __name__ == "__main__":
    main()
