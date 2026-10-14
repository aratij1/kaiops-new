import json
import time
import urllib.request
import urllib.error

GATEWAY_URL = "http://localhost:62673"
ALERT_ID_TERMINAL = "68340f18-622f-48df-85f3-2b59f8fcce0d"
ALERT_ID_JIRA = "08717f4c0d1248c7b40ceef54176c9f5"

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
    print("=== TESTING RCA WORKFLOW & PROCESSED-RESULT ===")
    
    # 1. Login
    code, auth = req_json(f"{GATEWAY_URL}/auth/login", method="POST", data={"username": "admin", "password": "Admin@123456"})
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Authenticated successfully.")

    # 2. Check processed-result for Jira Alert
    s_proc_jira, res_proc_jira = req_json(f"{GATEWAY_URL}/alerts/{ALERT_ID_JIRA}/processed-result", headers=headers)
    print(f"\nJira Alert ({ALERT_ID_JIRA}) processed-result: status={s_proc_jira}")
    if s_proc_jira == 200:
        data = res_proc_jira.get("data", res_proc_jira)
        print("  Keys:", list(data.keys()))
        rca = data.get("rca", {})
        print("  RCA Root Cause:", rca.get("root_cause"))
        print("  RCA Summary:", rca.get("summary"))
        print("  Evidence count:", len(data.get("evidence", [])))
        print("  Recommendations count:", len(data.get("recommendations", [])))

    # 3. Check processed-result for Terminal Alert
    s_proc_term, res_proc_term = req_json(f"{GATEWAY_URL}/alerts/{ALERT_ID_TERMINAL}/processed-result", headers=headers)
    print(f"\nTerminal Alert ({ALERT_ID_TERMINAL}) processed-result: status={s_proc_term}")
    if s_proc_term == 200:
        data = res_proc_term.get("data", res_proc_term)
        print("  Keys:", list(data.keys()))
        rca = data.get("rca", {})
        print("  RCA Root Cause:", rca.get("root_cause"))
        print("  RCA Summary:", rca.get("summary"))
        print("  Evidence count:", len(data.get("evidence", [])))
        print("  Recommendations count:", len(data.get("recommendations", [])))

    # 4. Trigger /analysis/alerts/{alert_id}/regenerate for Terminal Alert
    print(f"\nTriggering /analysis/alerts/{ALERT_ID_TERMINAL}/regenerate...")
    s_reg, res_reg = req_json(f"{GATEWAY_URL}/analysis/alerts/{ALERT_ID_TERMINAL}/regenerate", method="POST", data={"mode": "fresh"}, headers=headers)
    print(f"Regenerate response: status={s_reg}")
    print(f"Response data: {json.dumps(res_reg, indent=2)}")

    if s_reg in (200, 202):
        req_id = res_reg.get("request_id")
        inc_id = res_reg.get("incident_id")
        rec_id = res_reg.get("expected_recommendation_id")
        print(f"Request ID: {req_id}, Incident ID: {inc_id}")
        
        # Poll status
        for i in range(15):
            time.sleep(2)
            s_st, res_st = req_json(f"{GATEWAY_URL}/analysis/requests/{req_id}/status?incident_id={inc_id}", headers=headers)
            print(f"  Poll {i+1}: status={s_st}, data={res_st}")
            if res_st.get("status") in ("completed", "ready", "failed"):
                break
        
        # Check processed-result again
        s_proc_after, res_proc_after = req_json(f"{GATEWAY_URL}/alerts/{ALERT_ID_TERMINAL}/processed-result", headers=headers)
        print(f"\nTerminal Alert after regeneration: status={s_proc_after}")
        if s_proc_after == 200:
            data = res_proc_after.get("data", res_proc_after)
            print("  RCA Root Cause:", data.get("rca", {}).get("root_cause"))
            print("  RCA Summary:", data.get("rca", {}).get("summary"))
            print("  Evidence items:", len(data.get("evidence", [])))
            print("  Recommendations:", [r.get("title") for r in data.get("recommendations", [])])

if __name__ == "__main__":
    main()
