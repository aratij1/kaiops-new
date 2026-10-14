"""
Send 2 demo alerts for KaiMS demo recording.
Alert 1 = TEST  (Checkout Service Down)   → use this to verify the flow works
Alert 2 = VIDEO (RabbitMQ Service Down)   → use this when recording the demo video

Run:  python send_demo_alerts.py
"""
import urllib.request
import json
import subprocess
from datetime import datetime, timezone
import time


def send_alert(endpoint, payload, label):
    """Send alert by running python inside the monitoring-adapter container."""
    py_code = f"""
import urllib.request, json
req = urllib.request.Request(
    'http://127.0.0.1:8000{endpoint}',
    data={json.dumps(payload)!r}.encode('utf-8'),
    headers={{'Content-Type': 'application/json'}}
)
try:
    resp = urllib.request.urlopen(req, timeout=15)
    body = resp.read().decode()
    result = json.loads(body)
    print('STATUS  :', resp.status)
    print('Received:', result.get('received'))
    print('Ingested:', result.get('ingested'))
    print('Queued  :', result.get('queued'))
    print('Skipped :', result.get('skipped'))
    for a in result.get('alerts', []):
        print('  Alert  :', a.get('alertname'), '|', a.get('service'), '| action:', a.get('jira_action'))
except Exception as e:
    print('ERROR   :', e)
"""
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    res = subprocess.run(
        ["docker", "exec", "-i", "kaims-latest-monitoring-adapter-1", "python", "-c", py_code],
        capture_output=True, text=True, timeout=30
    )
    print(res.stdout.strip())
    if res.stderr.strip():
        print("STDERR:", res.stderr.strip())


now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
ts = int(time.time())


# ─────────────────────────────────────────────────────────────
# ALERT 1 — TEST ALERT
# Checkout Service Down (use this first to verify KaiMS picks it up)
# ─────────────────────────────────────────────────────────────
alert1 = {
    "version": "4",
    "groupKey": "{}:{alertname=\"CheckoutServiceDown\"}",
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
                "source_event_id": f"demo-checkout-test-{ts}"
            },
            "annotations": {
                "summary": "Robot Shop checkout service is unreachable",
                "description": "Prometheus cannot scrape rs-checkout:8080 for more than 30s. Orders cannot be placed."
            },
            "startsAt": now,
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph?g0.expr=up{job=\"robot-shop-checkout\"}==0",
            "fingerprint": f"checkout-down-{ts}"
        }
    ]
}

send_alert(
    "/alerts/alertmanager",
    alert1,
    "ALERT 1 — TEST  |  Checkout Service Down  |  Check this in the UI first"
)

print("\n>>> Go to http://localhost/ and check the Unified Inbox.")
print(">>> You should see a NEW Signal card: CheckoutServiceDown")
print(">>> Wait ~2-3 minutes for KaiMS to create an incident from it.")
print()
input(">>> Press ENTER when you are ready to send Alert 2 (the VIDEO alert)...")


# ─────────────────────────────────────────────────────────────
# ALERT 2 — VIDEO ALERT
# RabbitMQ Service Down (use this when recording the demo video)
# ─────────────────────────────────────────────────────────────
now2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
ts2 = int(time.time())

alert2 = {
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
                "source": "robot-shop",
                "application": "robot-shop",
                "project": "robot-shop",
                "project_name": "robot-shop",
                "job": "robot-shop-rabbitmq",
                "instance": "rs-rabbitmq-exporter:9419",
                "origin_system": "prometheus",
                "transport": "alertmanager",
                "source_event_id": f"demo-rabbitmq-video-{ts2}"
            },
            "annotations": {
                "summary": "Robot Shop dependency robot-shop-rabbitmq is unreachable",
                "description": "Prometheus cannot scrape robot-shop-rabbitmq for more than 20s. Message queue is unavailable."
            },
            "startsAt": now2,
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph?g0.expr=up{job=\"robot-shop-rabbitmq\"}==0",
            "fingerprint": f"rabbitmq-video-{ts2}"
        }
    ]
}

send_alert(
    "/alerts/alertmanager",
    alert2,
    "ALERT 2 — VIDEO  |  RobotShop RabbitMQ Service Down  |  Use this for the demo recording"
)

print()
print("="*55)
print("DONE. Both alerts sent.")
print("="*55)
print()
print("NEXT STEPS:")
print("  1. Open http://localhost/ in Chrome")
print("  2. Click 'Incidents' in the left sidebar")
print("  3. Look for 'RobotShopServiceDown' signal card")
print("  4. Wait 2-3 minutes — an incident will be created")
print("  5. Open the incident and follow the demo screens")
print()
