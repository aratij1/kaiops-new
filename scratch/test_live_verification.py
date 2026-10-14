import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:55112"

def request_json(url, method="GET", data=None, headers=None):
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
    print("1. Testing authentication...")
    code, auth_res = request_json(
        f"{BASE_URL}/auth/login",
        method="POST",
        data={"username": "admin", "password": "Admin@123456"}
    )
    print(f"Auth response: status={code}")
    assert code == 200, f"Failed auth: {auth_res}"
    token = auth_res.get("access_token")
    assert token, "No access_token received"
    headers = {"Authorization": f"Bearer {token}"}
    print("Authentication successful!")

    print("\n2. Testing /incidents/groups...")
    code, groups_res = request_json(f"{BASE_URL}/incidents/groups", headers=headers)
    print(f"Groups response: status={code}, keys={list(groups_res.keys()) if isinstance(groups_res, dict) else type(groups_res)}")
    assert code == 200

    print("\n3. Testing /incidents/inbox/feed...")
    code, feed_res = request_json(f"{BASE_URL}/incidents/inbox/feed", headers=headers)
    print(f"Feed response: status={code}")
    assert code == 200

    # Extract an incident ID from feed or groups
    incidents = []
    feed_data = feed_res.get("data") if isinstance(feed_res, dict) else feed_res
    groups_data = groups_res.get("data") if isinstance(groups_res, dict) else groups_res
    print("feed_data keys:", feed_data.keys() if isinstance(feed_data, dict) else type(feed_data))
    print("groups_data keys:", groups_data.keys() if isinstance(groups_data, dict) else type(groups_data))

    if isinstance(feed_data, dict):
        incidents = feed_data.get("items") or feed_data.get("incidents") or feed_data.get("rows") or []
    elif isinstance(feed_data, list):
        incidents = feed_data

    if not incidents and isinstance(groups_data, dict):
        incidents = groups_data.get("items") or groups_data.get("groups") or groups_data.get("rows") or []
    elif not incidents and isinstance(groups_data, list):
        incidents = groups_data

    print(f"Found {len(incidents)} incidents in feed/groups")
    sample_id = None
    for inc in incidents:
        inner = inc.get("row") if isinstance(inc, dict) and isinstance(inc.get("row"), dict) else inc
        cand = inner.get("id") or inner.get("incident_id")
        if cand and len(str(cand)) == 36 and "-" in str(cand):
            sample_id = str(cand)
            break

    if not sample_id and incidents:
        inner = incidents[0].get("row") if isinstance(incidents[0], dict) and isinstance(incidents[0].get("row"), dict) else incidents[0]
        sample_id = str(inner.get("id") or inner.get("incident_id"))

    print(f"Sample incident ID: {sample_id}")
    assert sample_id, "No sample incident found to test UUID normalization"

    hyphenated_id = sample_id
    hex_32_id = sample_id.replace("-", "")
    print(f"Hyphenated UUID: {hyphenated_id}")
    print(f"32-char Hex UUID: {hex_32_id}")

    print("\n4. Testing GET /incidents/{id}/command with hyphenated UUID...")
    code_hyphen, res_hyphen = request_json(f"{BASE_URL}/incidents/{hyphenated_id}/command", headers=headers)
    print(f"Hyphenated response status: {code_hyphen}")
    assert code_hyphen == 200, f"Failed hyphenated: {res_hyphen}"
    assert res_hyphen.get("incident_id") == hyphenated_id

    print("\n5. Testing GET /incidents/{id}/command with 32-character hex UUID...")
    code_hex, res_hex = request_json(f"{BASE_URL}/incidents/{hex_32_id}/command", headers=headers)
    print(f"Hex response status: {code_hex}")
    assert code_hex == 200, f"Failed hex: {res_hex}"
    assert res_hex.get("incident_id") == hyphenated_id, f"Expected canonical ID {hyphenated_id}, got {res_hex.get('incident_id')}"
    assert res_hex.get("revision") == res_hyphen.get("revision"), "Revisions should match exactly"

    print("\n6. Testing GET /incidents/{id}/command with invalid UUID...")
    invalid_id = "f874ad68-invalid-uuid-token"
    code_invalid, res_invalid = request_json(f"{BASE_URL}/incidents/{invalid_id}/command", headers=headers)
    print(f"Invalid UUID response status: {code_invalid}")
    print(f"Invalid UUID response body: {res_invalid}")
    assert code_invalid == 404, f"Expected 404 for invalid UUID, got {code_invalid}"

    print("\n7. Testing GET /incidents/{id} (basic projection) with both UUID representations...")
    code_base_h, res_base_h = request_json(f"{BASE_URL}/incidents/{hyphenated_id}", headers=headers)
    code_base_x, res_base_x = request_json(f"{BASE_URL}/incidents/{hex_32_id}", headers=headers)
    print(f"Base projection hyphenated status: {code_base_h}, hex status: {code_base_x}")
    assert code_base_h == 200 and code_base_x == 200

    print("\nALL ISSUE 3 LIVE TESTS PASSED!")

if __name__ == "__main__":
    main()
