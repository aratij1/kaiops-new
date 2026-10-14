import os
from pathlib import Path

env_path = Path(".env")
sensitive_keywords = ['SECRET', 'PASSWORD', 'TOKEN', 'KEY', 'CREDENTIAL', 'CONNECTION_STRING', 'AUTH']

print("=== .ENV VARIABLE STATUS (SAFE AUDIT - NO SECRETS PRINTED) ===")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        is_sensitive = any(w in key.upper() for w in sensitive_keywords)
        is_set = bool(val and not val.startswith("change-me") and not val.startswith("your_") and not val.startswith("<"))
        if is_sensitive:
            print(f"{key}: [CONFIGURED={is_set}] (value hidden)")
        else:
            print(f"{key}={val}")
else:
    print(".env file not found")
