import json
import urllib.request

GATEWAY_URL = "http://localhost:62673"

def req_json(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def main():
    code, auth = req_json(f"{GATEWAY_URL}/auth/login", method="POST", data={"username": "admin", "password": "Admin@123456"})
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    s_feed, res_feed = req_json(f"{GATEWAY_URL}/incidents/inbox/feed", headers=headers)
    rows = res_feed.get("data", {}).get("rows", [])
    print(f"Total incidents in inbox feed: {len(rows)}")

    for idx, item in enumerate(rows[:8]):
        row = item.get("row", item)
        inc_id = row.get("incident_id") or row.get("id")
        title = row.get("title")
        svc = row.get("service")
        status = row.get("status")
        jira = row.get("jira_key") or row.get("ticket_id")
        print(f"\n[{idx+1}] Incident {inc_id[:8]}... | Svc: {svc} | Jira: {jira} | Status: {status} | Title: {title}")

        # Check operations-state or processed-result
        s_op, res_op = req_json(f"{GATEWAY_URL}/incidents/{inc_id}/operations-state", headers=headers)
        if s_op == 200:
            inv = res_op.get("investigation_workspace", {})
            rca = inv.get("rca", {})
            hypo = inv.get("hypotheses", [])
            evi = inv.get("evidence", [])
            print(f"    Operations State -> RCA: {bool(rca)}, Hypotheses: {len(hypo)}, Evidence: {len(evi)}")
            if rca:
                print(f"    RCA Summary: {rca.get('summary')}")
                print(f"    RCA Root Cause: {rca.get('root_cause')}")

        # Check command workspace
        s_cmd, res_cmd = req_json(f"{GATEWAY_URL}/incidents/{inc_id}/command", headers=headers)
        if s_cmd == 200:
            ev = res_cmd.get("evidence", {})
            print(f"    Command Evidence Scores: {[sc.get('key') + ':' + str(sc.get('percent')) for sc in ev.get('scores', [])]}")

if __name__ == "__main__":
    main()
