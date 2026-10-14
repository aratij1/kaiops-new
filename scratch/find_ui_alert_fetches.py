with open("frontend/react/src/App.jsx", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re

# Find where /api-gateway/alerts and /api-gateway/incidents or /alerts are called
print("=== API CALLS FOR ALERTS AND INCIDENTS IN APP.JSX ===")
matches = [m.start() for m in re.finditer(r'/alerts|/incidents', text)]
for idx in matches[:15]:
    start = max(0, idx - 100)
    end = min(len(text), idx + 200)
    print(text[start:end])
    print("-" * 50)
