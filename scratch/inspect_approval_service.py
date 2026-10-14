with open("backend/src/approval-service/app.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
routes = re.findall(r'@app\.(post|get|put|delete)\(["\']([^"\']+)["\']', text)
print("Routes in approval-service:")
for m, r in routes:
    print(f"  {m.upper():6} {r}")

classes = re.findall(r'class ([a-zA-Z0-9_]+)\b', text)
print("\nClasses in approval-service:", classes)
