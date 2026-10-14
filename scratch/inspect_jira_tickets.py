import asyncio
import os
import sys
from dotenv import dotenv_values
import httpx

vals = dotenv_values(".env")
base_url = vals.get("JIRA_API_BASE_URL", "").rstrip("/")
email = vals.get("JIRA_API_EMAIL", "")
token = vals.get("JIRA_API_TOKEN", "")

async def main():
    print(f"=== CHECKING JIRA TICKETS ON {base_url} ===")
    auth = (email, token)
    async with httpx.AsyncClient(auth=auth, timeout=15.0) as client:
        for key in ["KAN-2202", "KAN-2203"]:
            resp = await client.get(f"{base_url}/rest/api/2/issue/{key}")
            print(f"\nTicket {key}: status={resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                fields = data.get("fields", {})
                print(f"  Summary: {fields.get('summary')}")
                print(f"  Status: {fields.get('status', {}).get('name')}")
                print(f"  Labels: {fields.get('labels')}")
                
                # Check comments
                comments_resp = await client.get(f"{base_url}/rest/api/2/issue/{key}/comment")
                if comments_resp.status_code == 200:
                    comments = comments_resp.json().get("comments", [])
                    print(f"  Total comments: {len(comments)}")
                    for c in comments[-3:]:
                        body = c.get("body", "")
                        print(f"    Author: {c.get('author', {}).get('displayName')} | Created: {c.get('created')}")
                        print(f"    Body snippet: {body[:150]}...")

if __name__ == "__main__":
    asyncio.run(main())
