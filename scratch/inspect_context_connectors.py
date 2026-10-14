with open("ai-workbench/src/context-agent/context_agent/connectors.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
classes = re.findall(r'class ([a-zA-Z0-9_]+)\b', text)
print("Classes in context_agent/connectors.py:")
for c in classes[:25]:
    print(" ", c)
