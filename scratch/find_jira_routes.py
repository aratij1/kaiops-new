from pathlib import Path

lines = Path("backend/src/monitoring-adapter/app.py").read_text(encoding="utf-8").splitlines()

for i, line in enumerate(lines, 1):
    if any(k in line for k in ["/jira", "jira_webhook", "webhook_jira", "jira_poll", "jira_issue", "Jira"]):
        if "@app." in line or "def " in line or "JQL" in line or "jql" in line or "webhook" in line.lower():
            print(f"{i}: {line}")
