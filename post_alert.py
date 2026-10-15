import json
import time
import urllib.request
from datetime import datetime, timezone

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
ts = int(time.time())

payload = {
    "version": "4",
    "groupKey": f"alertname=RobotShopServiceDown-{ts}",
    "truncatedAlerts": 0,
    "status": "firing",
    "receiver": "kaiops-landing-pad",
    "groupLabels": {"alertname": "RobotShopServiceDown", "severity": "critical"},
    "commonLabels": {
        "alertname": "RobotShopServiceDown",
        "severity": "critical",
        "source": "robot-shop",
        "application": "robot-shop",
        "project": "robot-shop",
        "project_name": "robot-shop",
        "job": "robot-shop-rabbitmq",
        "instance": "rs-rabbitmq-exporter:9419",
        "origin_system": "prometheus",
        "transport": "alertmanager",
    },
    "commonAnnotations": {
        "summary": "Robot Shop dependency robot-shop-rabbitmq is unreachable",
        "description": "Prometheus cannot scrape robot-shop-rabbitmq for more than 20s. Message queue is unavailable.",
    },
    "externalURL": "http://alertmanager:9093",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "RobotShopServiceDown",
                "severity": "critical",
                "source": "robot-shop",
                "application": "robot-shop",
                "project": "robot-shop",
                "project_name": "robot-shop",
                "job": "robot-shop-rabbitmq",
                "instance": "rs-rabbitmq-exporter:9419",
                "origin_system": "prometheus",
                "transport": "alertmanager",
                "source_event_id": f"live-rabbitmq-{ts}",
            },
            "annotations": {
                "summary": "Robot Shop dependency robot-shop-rabbitmq is unreachable",
                "description": "Prometheus cannot scrape robot-shop-rabbitmq for more than 20s. Message queue is unavailable.",
            },
            "startsAt": now,
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": 'http://prometheus:9090/graph?g0.expr=up{job="robot-shop-rabbitmq"}==0',
            "fingerprint": f"rabbitmq-live-{ts}",
        }
    ],
}

endpoints = [
    "http://127.0.0.1:8501/monitoring-adapter/alerts/alertmanager",
    "http://127.0.0.1/monitoring-adapter/alerts/alertmanager",
    "http://127.0.0.1:8000/alerts/alertmanager",
]

success = False
for url in endpoints:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"SUCCESS via {url}")
        print("STATUS:", resp.status)
        print("BODY  :", resp.read().decode())
        success = True
        break
    except Exception as e:
        print(f"Failed {url}: {e}")

if not success:
    print("ERROR: Could not connect to any monitoring adapter endpoint.")
