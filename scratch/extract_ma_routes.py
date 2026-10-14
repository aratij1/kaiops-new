import ast
import re

with open("backend/src/monitoring-adapter/app.py", "r", encoding="utf-8", errors="ignore") as f:
    code = f.read()

# Find all @app.post, @app.get, etc.
routes = re.findall(r'@app\.(post|get|put|delete|patch)\(["\']([^"\']+)["\']', code)
print(f"Total routes in monitoring-adapter app.py: {len(routes)}")
for m, r in routes:
    print(f"  {m.upper():6} {r}")
