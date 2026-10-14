with open("backend/src/remediation-engine/app.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
routes = re.findall(r'@app\.(post|get|put|delete)\(["\']([^"\']+)["\']', text)
print("Routes in remediation-engine:")
for m, r in routes:
    print(f"  {m.upper():6} {r}")
