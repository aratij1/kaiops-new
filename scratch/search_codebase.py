import os
from pathlib import Path

root = Path(".")
terms = ["corestack", "core_stack", "core-stack", "cloud-operations", "cloud_operations", "cloud inventory"]

matches = {t: [] for t in terms}

for p in root.rglob("*.py"):
    if ".git" in p.parts or "node_modules" in p.parts:
        continue
    try:
        text = p.read_text(encoding="utf-8", errors="ignore").lower()
        for t in terms:
            if t in text:
                matches[t].append(str(p))
    except Exception:
        pass

for p in [Path("docker-compose.yml"), Path("README.md")]:
    if p.exists():
        text = p.read_text(encoding="utf-8", errors="ignore").lower()
        for t in terms:
            if t in text:
                matches[t].append(str(p))

print("=== SEARCH RESULTS ===")
for t, files in matches.items():
    print(f"\nTerm: '{t}' -> {len(files)} files")
    for f in files[:10]:
        print(f"  - {f}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")
