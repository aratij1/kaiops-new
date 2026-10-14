with open("backend/src/monitoring-adapter/app.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

for target in ["def _build_alert_from_payload(", "def _publish_ingested_alert(", "def _ingest_provider_alert("]:
    idx = text.find(target)
    if idx != -1:
        print(f"=== {target} ===")
        print(text[idx:idx+1200])
        print("="*60)
