with open("backend/src/monitoring-adapter/app.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re

for ep in ["/alerts", "/api/v1/alerts/prometheus", "/api/v1/alerts/{provider}", "/api/v1/tickets/jira"]:
    m = re.search(r'@app\.post\(["\']' + re.escape(ep) + r'["\'].*?\n(?:async )?def ([a-zA-Z0-9_]+)\(', text)
    if m:
        fn = m.group(1)
        print(f"Endpoint {ep} -> Function: {fn}")
        # Find function definition start
        fn_start = text.find(f"def {fn}(")
        print(text[fn_start:fn_start+800])
        print("="*60)
