import json
import time
import urllib.request
from datetime import datetime, timezone

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
ts = int(time.time())

payload = {
    "version": "4",
    "groupKey": f"alertname=CheckoutServiceDown-{ts}",
    "truncatedAlerts": 0,
    "status": "firing",
    "receiver": "kaiops-landing-pad",
    "groupLabels": {"alertname": "CheckoutServiceDown", "severity": "critical"},
    "commonLabels": {
        "alertname": "CheckoutServiceDown",
        "severity": "critical",
        "application": "robot-shop",
        "project": "robot-shop",
        "project_name": "robot-shop",
        "job": "robot-shop-checkout",
        "instance": "rs-checkout:8080",
        "origin_system": "prometheus",
        "transport": "alertmanager",
    },
    "commonAnnotations": {
        "summary": "Robot Shop checkout service is unreachable",
        "description": "Prometheus cannot scrape rs-checkout:8080 for more than 30s. Orders cannot be placed.",
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
                "source_event_id": f"live-checkout-{ts}",
            },
            "annotations": {
                "summary": "Robot Shop checkout service is unreachable",
                "description": "Prometheus cannot scrape rs-checkout:8080 for more than 30s. Orders cannot be placed.",
            },
            "startsAt": now,
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": 'http://prometheus:9090/graph?g0.expr=up{job="robot-shop-checkout"}==0',
            "fingerprint": f"checkout-live-{ts}",
        }
    ],
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/alerts/alertmanager",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

try:
    resp = urllib.request.urlopen(req, timeout=15)
    print("STATUS:", resp.status)
    print("BODY  :", resp.read().decode())
except Exception as e:
    print("ERROR :", e)
