import re
from pathlib import Path

base_dir = Path("c:/Users/arati.joshi/Desktop/kaims-latest/kaims-latest")

print("=== 1. REDIS USAGE IN CODEBASE ===")
redis_calls = []
for p in base_dir.rglob("*.py"):
    if any(ignore in p.parts for ignore in [".git", "node_modules", ".pytest_cache", "venv"]):
        continue
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(r"\bredis\b", line, re.I) or re.search(r"\.get\(|\.set\(|\.setex\(|\.expire\(", line):
                if any(k in line.lower() for k in ["redis", "dedup", "fingerprint", "cache"]):
                    redis_calls.append(f"{p.relative_to(base_dir)}:{i}: {line.strip()}")
    except Exception:
        pass

print(f"Total Redis-related code occurrences: {len(redis_calls)}")
for call in redis_calls[:20]:
    print("  ", call)

print("\n=== 2. POSTGRESQL USAGE IN CODEBASE ===")
for p in base_dir.rglob("*.py"):
    if any(ignore in p.parts for ignore in [".git", "node_modules", ".pytest_cache", "venv"]):
        continue
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
        if "postgres" in content.lower():
            print(f"Found postgres in: {p.relative_to(base_dir)}")
            for i, line in enumerate(content.splitlines(), 1):
                if "postgres" in line.lower():
                    print(f"   L{i}: {line.strip()}")
    except Exception:
        pass

print("\n=== 3. BACKEND/RAG DIRECTORY AND FILES ===")
rag_dir = base_dir / "backend" / "rag"
if not rag_dir.exists():
    rag_dir = Path("c:/Users/arati.joshi/Desktop/kaims-latest/backend/rag")
if rag_dir.exists():
    rag_files = list(rag_dir.rglob("*"))
    print(f"RAG files count: {len(rag_files)} in {rag_dir}")
    md_files = [f for f in rag_files if f.suffix == ".md"]
    print(f"Markdown runbooks/incident files ({len(md_files)}):")
    for f in md_files[:15]:
        print(f"   - {f.name}")
    if len(md_files) > 15:
        print(f"   ... and {len(md_files) - 15} more")
    if (rag_dir / "scenarios.txt").exists():
        print("scenarios.txt found!")
else:
    print("RAG dir not found!")
