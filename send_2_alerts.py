import urllib.request
import json
import subprocess
import time
from datetime import datetime, timezone

ts = int(time.time())
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

alerts = [
    {
        "name": "PaymentGatewayLatencyHigh",
        "payload": {
            "version": "4",
            "groupKey": '{}:{alertname="PaymentGatewayLatencyHigh"}',
            "status": "firing",
            "receiver": "kaiops-landing-pad",
            "groupLabels": {"alertname": "PaymentGatewayLatencyHigh", "severity": "critical"},
            "commonLabels": {
                "alertname": "PaymentGatewayLatencyHigh",
                "severity": "critical",
                "application": "payment-gateway",
                "project": "payment-gateway",
                "project_name": "payment-gateway",
                "job": "payment-gateway",
                "instance": "payment-gateway:8080",
                "origin_system": "prometheus"
            },
            "commonAnnotations": {
                "summary": "Payment Gateway latency exceeds 2.5s threshold",
                "description": "P99 transaction latency for payment-gateway is 2850ms, breaching SLA."
            },
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": "PaymentGatewayLatencyHigh",
                    "severity": "critical",
                    "application": "payment-gateway",
                    "project": "payment-gateway",
                    "job": "payment-gateway",
                    "instance": "payment-gateway:8080",
                    "source_event_id": f"pg-lat-{ts}"
                },
                "annotations": {
                    "summary": "Payment Gateway latency exceeds 2.5s threshold",
                    "description": "P99 transaction latency for payment-gateway is 2850ms, breaching SLA."
                },
                "startsAt": now,
                "fingerprint": f"pg-lat-{ts}"
            }]
        }
    },
    {
        "name": "CheckoutServiceDown",
        "payload": {
            "version": "4",
            "groupKey": '{}:{alertname="CheckoutServiceDown"}',
            "status": "firing",
            "receiver": "kaiops-landing-pad",
            "groupLabels": {"alertname": "CheckoutServiceDown", "severity": "critical"},
            "commonLabels": {
                "alertname": "CheckoutServiceDown",
                "severity": "critical",
                "application": "payment-gateway",
                "project": "payment-gateway",
                "project_name": "payment-gateway",
                "job": "payment-gateway-checkout",
                "instance": "checkout:8080",
                "origin_system": "prometheus"
            },
            "commonAnnotations": {
                "summary": "Checkout service endpoint unreachable",
                "description": "Checkout service returned 503 Service Unavailable."
            },
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": "CheckoutServiceDown",
                    "severity": "critical",
                    "application": "payment-gateway",
                    "project": "payment-gateway",
                    "job": "payment-gateway-checkout",
                    "instance": "checkout:8080",
                    "source_event_id": f"pg-checkout-{ts}"
                },
                "annotations": {
                    "summary": "Checkout service endpoint unreachable",
                    "description": "Checkout service returned 503 Service Unavailable."
                },
                "startsAt": now,
                "fingerprint": f"pg-checkout-{ts}"
            }]
        }
    }
]

for item in alerts:
    name = item["name"]
    payload = item["payload"]
    py_code = f"""
import urllib.request, json
req = urllib.request.Request(
    'http://127.0.0.1:8000/alerts/alertmanager',
    data={json.dumps(payload)!r}.encode('utf-8'),
    headers={{'Content-Type': 'application/json'}}
)
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print('Sent {name}: HTTP', resp.status, resp.read().decode())
except Exception as e:
    print('Error:', e)
"""
    res = subprocess.run([
        "docker", "exec", "-i", "kaims-latest-monitoring-adapter-1", "python", "-c", py_code
    ], capture_output=True, text=True)
    print(res.stdout.strip())
    if res.stderr.strip():
        print("STDERR:", res.stderr.strip())
