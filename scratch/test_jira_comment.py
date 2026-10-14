import asyncio
import os
import sys

sys.path.insert(0, "/app/backend/src/common")
sys.path.insert(0, "/app/backend/src/monitoring-adapter")

from monitoring_adapter.jira_client import JiraClient

async def test_jira_comment():
    base_url = os.getenv("JIRA_API_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_API_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    project_key = os.getenv("JIRA_PROJECT_KEY", "KAN")

    client = JiraClient(
        base_url=base_url,
        email=email,
        api_token=token,
        project_key=project_key,
    )

    issue_key = "KAN-2202"
    comment_text = "KAIMS Live Verification: Incident f5e8a0f0-5378-40dd-af4e-4f764e5e7e64 correlated. Context and evidence collection started by KAIMS Context Agent."
    print(f"Posting comment to Jira issue {issue_key}...")
    await client.add_comment(issue_key, comment_text)
    print("Comment posted successfully!")

    # Verify by getting issue comments
    import httpx
    async with httpx.AsyncClient(auth=(email, token), timeout=15.0) as http_client:
        r = await http_client.get(f"{base_url}/rest/api/2/issue/{issue_key}/comment")
        comments = r.json().get("comments", [])
        print(f"Verified {len(comments)} comment(s) on {issue_key}:")
        for c in comments:
            body = c.get("body")
            author = c.get("author", {}).get("displayName")
            print(f"  - Author: {author} | Body: {body}")

if __name__ == "__main__":
    asyncio.run(test_jira_comment())
