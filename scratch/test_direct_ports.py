import socket
import urllib.request

PORTS = [
    (8501, "UI (port 8501)", "/"),
    (80, "UI (port 80)", "/"),
    (51441, "api-gateway", "/healthz"),
    (51442, "monitoring-adapter", "/healthz"),
    (51443, "orchestrator", "/healthz"),
    (51444, "discovery-mcp", "/healthz"),
    (51445, "remediation-engine", "/healthz"),
    (51446, "alert-intelligence", "/healthz"),
    (51447, "closure-service", "/healthz"),
    (51448, "application-onboarding", "/healthz"),
    (51449, "context-agent", "/healthz"),
    (51450, "resolution-agent", "/healthz"),
    (51440, "model-router", "/healthz"),
    (8012, "discovery-service", "/healthz"),
    (8013, "metrics-validation-agent", "/healthz"),
    (8014, "rule-generation-agent", "/healthz"),
    (8015, "prometheus-config-service", "/healthz"),
    (8016, "validation-agent", "/healthz"),
    (8017, "dashboard-generator", "/healthz"),
    (8018, "audit-service", "/healthz"),
    (8019, "notification-service", "/healthz"),
    (8020, "evaluation-service", "/healthz"),
    (8022, "knowledge-development-worker", "/healthz"),
    (8027, "cloud-operations", "/healthz"),
    (8028, "connector-hub", "/healthz"),
    (3307, "mysql", None),
    (6380, "redis", None),
    (5672, "rabbitmq", None),
]

print("=== Direct Port Connectivity Test ===")
for port, name, path in PORTS:
    # Test raw TCP connection
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        tcp_ok = True
    except Exception as e:
        tcp_ok = False
        print(f"[FAIL] {name:30} Port {port:5}: TCP Connect Failed ({type(e).__name__})")
        continue

    if path:
        url = f"http://127.0.0.1:{port}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HealthProbe"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                print(f"[ OK ] {name:30} Port {port:5}: HTTP {resp.status}")
        except Exception as e:
            print(f"[WARN] {name:30} Port {port:5}: TCP Open, HTTP Failed ({e})")
    else:
        print(f"[ OK ] {name:30} Port {port:5}: TCP Open")
