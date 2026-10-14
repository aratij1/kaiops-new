import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

# Append common and monitoring-adapter paths
sys.path.insert(0, "/app/backend/src/common")
sys.path.insert(0, "/app/backend/src/monitoring-adapter")

from monitoring_adapter.jira_client import JiraClient

async def test_jira():
    base_url = os.getenv("JIRA_API_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_API_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    project_key = os.getenv("JIRA_PROJECT_KEY", "KAN")

    print(f"Testing connection to Jira instance: {base_url}")
    print(f"Jira User Email configured: {bool(email and email.strip())}")
    print(f"Jira API Token configured: {bool(token and token.strip())}")
    print(f"Jira Project Key: {project_key}")

    client = JiraClient(
        base_url=base_url,
        email=email,
        api_token=token,
        project_key=project_key,
    )

    try:
        # Search issues updated in the last 7 days
        since = datetime.now(UTC) - timedelta(days=7)
        issues = await client.search_updated_issues(updated_since=since, limit=5)
        print(f"Jira API Connection SUCCESSFUL! Fetched {len(issues)} issues from project {project_key}.")
        for issue in issues[:3]:
            key = issue.get("key")
            fields = issue.get("fields", {})
            summary = fields.get("summary")
            status = fields.get("status", {}).get("name")
            print(f"  - Key: {key} | Status: {status} | Summary: {summary[:60] if summary else 'N/A'}")
    except Exception as e:
        print(f"Jira API Connection FAILED: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_jira())
