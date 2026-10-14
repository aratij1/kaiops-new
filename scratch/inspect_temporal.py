import os
from pathlib import Path

temporal_dir = Path("backend/src/temporal-pilot")
if temporal_dir.exists():
    for p in temporal_dir.rglob("*.py"):
        print(f"File: {p}")
        text = p.read_text(encoding="utf-8", errors="ignore")
        print("  Size:", len(text))
        lines = [l.strip() for l in text.splitlines() if "@workflow" in l or "@activity" in l or "class " in l]
        print("  Workflow/Activity/Classes:", lines[:10])
