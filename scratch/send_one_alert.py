import json
import subprocess
import time
from datetime import datetime, timezone

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
ts = int(time.time())

alert = {
    "version": "4",
    "groupKey": f"{{}}:{{alertname=\"RobotShopServiceDown\"}}",
    "truncatedAlerts": 0,
    "status": "firing",
    "receiver": "kaiops-landing-pad",
    "groupLabels": {
        "alertname": "RobotShopServiceDown",
        "severity": "critical"
    },
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
        "transport": "alertmanager"
    },
    "commonAnnotations": {
        "summary": "Robot Shop dependency robot-shop-rabbitmq is unreachable",
        "description": "Prometheus cannot scrape robot-shop-rabbitmq for more than 20s. Message queue is unavailable."
    },
    "externalURL": "http://alertmanager:9093",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "RobotShopServiceDown",
                "severity": "critical",
                "service": "robot-shop-rabbitmq",
                "source": "robot-shop",
                "application": "robot-shop",
                "project": "robot-shop",
                "project_name": "robot-shop",
                "job": "robot-shop-rabbitmq",
                "instance": "rs-rabbitmq-exporter:9419",
                "origin_system": "prometheus",
                "transport": "alertmanager",
                "source_event_id": f"demo-rabbitmq-{ts}"
            },
            "annotations": {
                "summary": "Robot Shop dependency robot-shop-rabbitmq is unreachable",
                "description": "Prometheus cannot scrape robot-shop-rabbitmq for more than 20s. Message queue is unavailable."
            },
            "startsAt": now,
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph?g0.expr=up{job=\"robot-shop-rabbitmq\"}==0",
            "fingerprint": f"rabbitmq-down-{ts}"
        }
    ]
}

py_code = f"""
import urllib.request, json
req = urllib.request.Request(
    'http://127.0.0.1:8000/alerts/alertmanager',
    data={json.dumps(alert)!r}.encode('utf-8'),
    headers={{'Content-Type': 'application/json'}}
)
try:
    resp = urllib.request.urlopen(req, timeout=15)
    body = resp.read().decode()
    print('STATUS:', resp.status)
    print('BODY:', body)
except Exception as e:
    print('ERROR:', e)
"""

res = subprocess.run(
    ["docker", "exec", "-i", "kaims-latest-monitoring-adapter-1", "python", "-c", py_code],
    capture_output=True, text=True, timeout=30
)
print("OUT:", res.stdout.strip())
if res.stderr.strip():
    print("ERR:", res.stderr.strip())
