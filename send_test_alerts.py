import urllib.request
import json
import subprocess
from datetime import datetime, timezone

def send_alert(endpoint, payload):
    py_code = f"""
import urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:8000{endpoint}',
    data={json.dumps(payload)!r}.encode('utf-8'),
    headers={{'Content-Type': 'application/json'}}
)
try:
    resp = urllib.request.urlopen(req)
    print('STATUS:', resp.status)
    print('BODY:', resp.read().decode())
except Exception as e:
    print('ERR:', e)
"""
    res = subprocess.run([
        "docker", "exec", "-i", "kaims-latest-monitoring-adapter-1",
        "python", "-c", py_code
    ], capture_output=True, text=True)
    print("STDOUT:", res.stdout.strip())
    if res.stderr.strip():
        print("STDERR:", res.stderr.strip())

now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

print("--- Sending Alert 1: OpenSearch Log Burst Alert (Will stay UNCLOSED/Investigating) ---")
with open("samples/landing-pad/kaiops-log-alert.json") as f:
    log_payload = json.load(f)
log_payload["labels"]["source_event_id"] = f"log-test-{int(datetime.now().timestamp())}"
log_payload["timestamp"] = now_str
send_alert("/alerts/opensearch", log_payload)

print("\n--- Sending Alert 2: Prometheus RobotShop RabbitMQ Alert (Resolvable with Action) ---")
prom_payload = {
    "version": "4",
    "groupKey": "{}:{alertname=\"RobotShopServiceDown\"}",
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
        "instance": "rs-rabbitmq-exporter:9419"
    },
    "commonAnnotations": {
        "summary": "Robot Shop dependency robot-shop-rabbitmq is unreachable",
        "description": "Prometheus cannot scrape robot-shop-rabbitmq for more than 20s."
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
                "source_event_id": f"prom-test-{int(datetime.now().timestamp())}"
            },
            "annotations": {
                "summary": "Robot Shop dependency robot-shop-rabbitmq is unreachable",
                "description": "Prometheus cannot scrape robot-shop-rabbitmq for more than 20s."
            },
            "startsAt": now_str,
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090",
            "fingerprint": f"test-{int(datetime.now().timestamp())}"
        }
    ]
}
send_alert("/alerts/alertmanager", prom_payload)
