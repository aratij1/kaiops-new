import os

keys = [
    'JIRA_API_BASE_URL', 'JIRA_API_EMAIL', 'JIRA_PROJECT_KEY',
    'CENTRALIZED_JIRA_ROUTING_ENABLED', 'JIRA_POLLING_ENABLED',
    'JIRA_WEBHOOK_SECRET', 'JIRA_API_TOKEN'
]
print("=== MONITORING ADAPTER JIRA ENV AUDIT ===")
for k in keys:
    v = os.getenv(k)
    is_set = bool(v and str(v).strip())
    if 'SECRET' in k or 'TOKEN' in k:
        print(f"{k}: loaded={is_set}")
    else:
        print(f"{k}={v}")
