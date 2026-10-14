with open("frontend/react/src/App.jsx", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
endpoints = re.findall(r'fetchJson\(["\`](/[^"\`?]+)', text)
print("Unique endpoints fetched in App.jsx:")
for ep in sorted(set(endpoints)):
    print(" ", ep)
