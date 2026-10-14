import urllib.request
import json
import sys

gateway_url = "http://127.0.0.1:58219"

def trigger_workflow(flow_id="payment-latency"):
    url = f"{gateway_url}/sample/{flow_id}/workflow"
    print(f"Triggering {url}...")
    req = urllib.request.Request(url, data=json.dumps({}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            print("Status:", resp.status)
            print(json.dumps(data, indent=2))
            return data
    except Exception as e:
        print("Error triggering workflow:", e)
        if hasattr(e, "read"):
            print("Response body:", e.read().decode())
        sys.exit(1)

if __name__ == "__main__":
    flow = sys.argv[1] if len(sys.argv) > 1 else "payment-latency"
    trigger_workflow(flow)
