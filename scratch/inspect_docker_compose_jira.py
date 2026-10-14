from pathlib import Path

lines = Path("docker-compose.yml").read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines, 1):
    if any(k in line for k in ["JIRA", "jira"]):
        print(f"{i}: {line}")
