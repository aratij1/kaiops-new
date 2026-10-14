with open("ai-workbench/src/model-router/model_router/router.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
classes = re.findall(r'class ([a-zA-Z0-9_]+)\b', text)
print("Classes in model_router/router.py:", classes)

# Find providers supported
providers = re.findall(r'provider\s*==\s*["\']([^"\']+)["\']', text)
print("Providers in conditions:", set(providers))

# Find routes or main function
fns = re.findall(r'def ([a-zA-Z0-9_]+)\(', text)
print("Functions:", fns[:20])
