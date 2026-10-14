import json
import urllib.request

GATEWAY_URL = "http://localhost:62673"
ALERT_ID_TERMINAL = "68340f18-622f-48df-85f3-2b59f8fcce0d"
REQUEST_ID = "4148b8d6-d02f-4b40-9c94-35896011b41c"
INCIDENT_ID = "0d367082-ed9a-4b18-86dd-ad9826bbbcd9"

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

    s_st, res_st = req_json(f"{GATEWAY_URL}/analysis/requests/{REQUEST_ID}/status?incident_id={INCIDENT_ID}", headers=headers)
    print(f"Request Status: {s_st}")
    print(json.dumps(res_st, indent=2))

    s_proc, res_proc = req_json(f"{GATEWAY_URL}/alerts/{ALERT_ID_TERMINAL}/processed-result", headers=headers)
    print(f"\nProcessed Result: {s_proc}")
    data = res_proc.get("data", res_proc)
    print("RCA:", json.dumps(data.get("rca"), indent=2))
    print("Recommendations:", json.dumps(data.get("recommendations"), indent=2))
    print("Evidence:", len(data.get("evidence", [])))
    print("Decision:", json.dumps(data.get("decision"), indent=2))

    s_op, res_op = req_json(f"{GATEWAY_URL}/incidents/{INCIDENT_ID}/operations-state", headers=headers)
    print(f"\nOperations State: {s_op}")
    inv = res_op.get("investigation_workspace", {})
    print("Operations State RCA:", json.dumps(inv.get("rca"), indent=2))
    print("Operations State Hypotheses:", json.dumps(inv.get("hypotheses"), indent=2))

if __name__ == "__main__":
    main()
