import json
import ssl
import time
import urllib.request
from datetime import datetime, timezone

TARGET_BASE = "https://dgsl-aicoe-shannon.centralindia.cloudapp.azure.com"
ctx = ssl._create_unverified_context()

def send_alertmanager_alert(payload, label):
    url = f"{TARGET_BASE}/monitoring-adapter/alerts/alertmanager"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    print(f"\n{'='*60}")
    print(f"Sending to {url}: {label}")
    print(f"{'='*60}")
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=20)
        body = resp.read().decode("utf-8")
        print("HTTP Status:", resp.status)
        try:
            res_json = json.loads(body)
            print("Response:", json.dumps(res_json, indent=2))
        except Exception:
            print("Response Body:", body)
        return True
    except Exception as e:
        print("Error sending alert:", e)
        if hasattr(e, "read"):
            print("Error details:", e.read().decode("utf-8"))
        return False

if __name__ == "__main__":
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    ts = int(time.time())

    # Alert 1: Checkout Service Down
    alert1 = {
        "version": "4",
        "groupKey": f"{{}}:{{alertname=\"CheckoutServiceDown\"}}",
        "truncatedAlerts": 0,
        "status": "firing",
        "receiver": "kaiops-landing-pad",
        "groupLabels": {
            "alertname": "CheckoutServiceDown",
            "severity": "critical"
        },
        "commonLabels": {
            "alertname": "CheckoutServiceDown",
            "severity": "critical",
            "application": "robot-shop",
            "project": "robot-shop",
            "project_name": "robot-shop",
            "job": "robot-shop-checkout",
            "instance": "rs-checkout:8080",
            "origin_system": "prometheus",
            "transport": "alertmanager"
        },
        "commonAnnotations": {
            "summary": "Robot Shop checkout service is unreachable",
            "description": "Prometheus cannot scrape rs-checkout:8080 for more than 30s. Orders cannot be placed."
        },
        "externalURL": "http://alertmanager:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "CheckoutServiceDown",
                    "severity": "critical",
                    "application": "robot-shop",
                    "project": "robot-shop",
                    "project_name": "robot-shop",
                    "job": "robot-shop-checkout",
                    "instance": "rs-checkout:8080",
                    "origin_system": "prometheus",
                    "transport": "alertmanager",
                    "source_event_id": f"azure-checkout-{ts}"
                },
                "annotations": {
                    "summary": "Robot Shop checkout service is unreachable",
                    "description": "Prometheus cannot scrape rs-checkout:8080 for more than 30s. Orders cannot be placed."
                },
                "startsAt": now_str,
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph?g0.expr=up{job=\"robot-shop-checkout\"}==0",
                "fingerprint": f"checkout-azure-{ts}"
            }
        ]
    }

    send_alertmanager_alert(alert1, "Alert 1: CheckoutServiceDown (Robot Shop)")
