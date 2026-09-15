from datetime import UTC, datetime

import httpx
import pytest
from monitoring_adapter.jira_client import JiraClient


@pytest.mark.asyncio
async def test_jira_client_uses_configured_project_issue_type_and_basic_auth(monkeypatch):
    requests = []

    async def request(self, method, url, **kwargs):
        requests.append((method, url, kwargs))
        return httpx.Response(201, json={"key": "KAN-42"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    client = JiraClient(
        "https://kaiops-test.atlassian.net", "service@example.com", "secret-token", "KAN", "Bug"
    )
    key = await client.create_issue(
        summary="Checkout incident", description="Bound incident details", severity="critical"
    )
    assert key == "KAN-42"
    payload = requests[0][2]["json"]["fields"]
    assert payload["project"] == {"key": "KAN"}
    assert payload["issuetype"] == {"name": "Bug"}
    assert client._auth == ("service@example.com", "secret-token")


@pytest.mark.asyncio
async def test_jira_reconciliation_uses_overlapping_ordered_cursor(monkeypatch):
    captured = {}

    async def request(self, method, url, **kwargs):
        captured.update(kwargs["params"])
        return httpx.Response(200, json={"issues": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    client = JiraClient("https://kaiops-test.atlassian.net", "svc@example.com", "token", "KAN")
    await client.search_updated_issues(updated_since=datetime(2026, 8, 30, 10, 5, tzinfo=UTC))
    assert 'project = "KAN"' in captured["jql"]
    assert 'updated >= "2026-08-30 10:05"' in captured["jql"]
    assert "ORDER BY updated ASC, key ASC" in captured["jql"]


@pytest.mark.asyncio
async def test_jira_client_find_assignable_user_matches_display_name_and_email(monkeypatch):
    candidates = [
        {"accountId": "acc-123", "displayName": "Alice Admin", "emailAddress": "alice@example.com"},
        {"accountId": "acc-456", "displayName": "Bob Dev", "emailAddress": "bob@example.com"},
    ]

    async def request(self, method, url, **kwargs):
        assert method == "GET"
        assert "/rest/api/3/user/assignable/search" in url
        assert kwargs["params"]["project"] == "KAN"
        return httpx.Response(200, json=candidates, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    client = JiraClient("https://kaiops-test.atlassian.net", "svc@example.com", "token", "KAN")
    
    # Match by display name
    account_id = await client.find_assignable_user("Alice Admin")
    assert account_id == "acc-123"

    # Match by email
    account_id = await client.find_assignable_user("bob@example.com")
    assert account_id == "acc-456"

    # Match by accountId directly
    account_id = await client.find_assignable_user("acc-123")
    assert account_id == "acc-123"

    # Empty query returns None without calling Jira
    assert await client.find_assignable_user("") is None


@pytest.mark.asyncio
async def test_jira_client_add_labels_sends_update_payload(monkeypatch):
    requests = []

    async def request(self, method, url, **kwargs):
        requests.append((method, url, kwargs))
        return httpx.Response(204, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    client = JiraClient("https://kaiops-test.atlassian.net", "svc@example.com", "token", "KAN")
    await client.add_labels("KAN-101", ["kaiops-team-core-payments", "custom-tag"])

    assert len(requests) == 1
    method, url, kwargs = requests[0]
    assert method == "PUT"
    assert "/rest/api/3/issue/KAN-101" in url
    assert kwargs["json"] == {
        "update": {
            "labels": [
                {"add": "kaiops-team-core-payments"},
                {"add": "custom-tag"},
            ]
        }
    }
