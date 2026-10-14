import os
import re
from pathlib import Path

base_dir = Path("c:/Users/arati.joshi/Desktop/kaims-latest/kaims-latest")

services = [
    "monitoring-adapter",
    "alert-intelligence",
    "orchestrator",
    "context-agent",
    "resolution-agent",
    "approval-service",
    "remediation-engine",
    "closure-service",
    "notification-service",
    "model-router",
]

print("=== SERVICE APP.PY ENTRYPOINTS & CONSUMERS ===")
for svc in services:
    # search in backend/src or ai-workbench/src
    candidates = list(base_dir.rglob(f"{svc}/**/app.py"))
    if not candidates:
        candidates = list(base_dir.rglob(f"{svc}/app.py"))
    print(f"\nService: {svc}")
    for c in candidates:
        rel = c.relative_to(base_dir)
        print(f"  File: {rel}")
        content = c.read_text(encoding="utf-8", errors="ignore")
        # Look for consumers, exchanges, topics, routes
        routes = re.findall(r"@app\.(get|post|put|delete)\([\"']([^\"']+)[\"']", content)
        print(f"  Routes ({len(routes)}):")
        for method, path in routes[:6]:
            print(f"    - {method.upper()} {path}")
        if len(routes) > 6:
            print(f"    ... and {len(routes) - 6} more")
        
        # Check consumer/subscriber
        consumers = re.findall(r"(consume_events|subscribe|listen|channel|RabbitMQConsumer|consume_loop|on_message|process_event)\w*", content)
        if consumers:
            print(f"  Consumer markers: {set(consumers)}")
