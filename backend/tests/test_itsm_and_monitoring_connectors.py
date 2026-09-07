from __future__ import annotations

import httpx
import pytest

from common.cloud_operations.connectors import connector_for
from common.cloud_operations.itsm_connectors import AzureDevOpsConnector, JiraConnector, ServiceNowConnector
from common.cloud_operations.models import CloudConnection, DiscoveryRequest, ProviderType
from common.cloud_operations.secret_refs import SecretResolutionError, resolve_secret_ref
from common.cloud_operations.telemetry_connectors import DatadogConnector, DynatraceConnector, GrafanaConnector, PrometheusConnector


def _connection(*, connector_id: str, discovery_scope: dict, credential_ref: str, provider_type: ProviderType) -> CloudConnection:
    return CloudConnection(
        tenant_id="tenant-a", project_id="project-a", connection_name=f"{connector_id}-connection",
        provider_type=provider_type, credential_ref=credential_ref, connection_owner="admin@example.com",
        discovery_scope={"connector_id": connector_id, **discovery_scope},
    )


def _request() -> DiscoveryRequest:
    return DiscoveryRequest(tenant_id="tenant-a", project_id="project-a", service_id="checkout-api", environment="prod")


# --- secret_refs ---------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_secret_ref_reads_the_named_environment_variable(monkeypatch):
    monkeypatch.setenv("KAIMS_TEST_TOKEN", "s3cr3t")
    assert await resolve_secret_ref("env://KAIMS_TEST_TOKEN") == "s3cr3t"


@pytest.mark.asyncio
async def test_resolve_secret_ref_rejects_unconfigured_schemes():
    with pytest.raises(SecretResolutionError, match="vault"):
        await resolve_secret_ref("vault://kaiops/jira/token")


@pytest.mark.asyncio
async def test_resolve_secret_ref_fails_closed_when_variable_is_unset(monkeypatch):
    monkeypatch.delenv("KAIMS_TEST_TOKEN_MISSING", raising=False)
    with pytest.raises(SecretResolutionError, match="unavailable"):
        await resolve_secret_ref("env://KAIMS_TEST_TOKEN_MISSING")


# --- dispatch --------------------------------------------------------------

def test_connector_for_dispatches_itsm_by_connector_id():
    assert isinstance(connector_for(ProviderType.ITSM, connector_id="jira"), JiraConnector)
    assert isinstance(connector_for(ProviderType.ITSM, connector_id="servicenow"), ServiceNowConnector)
    assert isinstance(connector_for(ProviderType.ITSM, connector_id="azure_devops"), AzureDevOpsConnector)


def test_connector_for_rejects_unknown_itsm_connector_id():
    with pytest.raises(NotImplementedError, match="confluence"):
        connector_for(ProviderType.ITSM, connector_id="confluence")


def test_connector_for_dispatches_monitoring_by_connector_id():
    assert isinstance(connector_for(ProviderType.MONITORING, connector_id="prometheus"), PrometheusConnector)
    assert isinstance(connector_for(ProviderType.MONITORING, connector_id="grafana"), GrafanaConnector)
    assert isinstance(connector_for(ProviderType.MONITORING, connector_id="datadog"), DatadogConnector)


# --- Jira --------------------------------------------------------------

@pytest.mark.asyncio
async def test_jira_validate_connection_succeeds_with_basic_auth(monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "tok-123")
    seen = {}

    async def request(self, method, url, **kwargs):
        seen["url"] = str(url)
        seen["auth"] = kwargs.get("auth")
        return httpx.Response(200, json={"accountId": "abc"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="jira", provider_type=ProviderType.ITSM, credential_ref="env://JIRA_TOKEN",
        discovery_scope={"base_url": "https://acme.atlassian.net", "email": "bot@acme.com"},
    )
    result = await JiraConnector().validate_connection(connection)
    assert result.status == "validated"
    assert seen["url"].endswith("/rest/api/2/myself")


@pytest.mark.asyncio
async def test_jira_validate_connection_fails_closed_on_bad_credentials(monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "wrong")

    async def request(self, method, url, **kwargs):
        return httpx.Response(401, text="Unauthorized", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="jira", provider_type=ProviderType.ITSM, credential_ref="env://JIRA_TOKEN",
        discovery_scope={"base_url": "https://acme.atlassian.net", "email": "bot@acme.com"},
    )
    result = await JiraConnector().validate_connection(connection)
    assert result.status == "failed"
    assert result.connectivity_ok is False


@pytest.mark.asyncio
async def test_jira_discover_resources_maps_projects_to_discovered_resources(monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "tok-123")

    async def request(self, method, url, **kwargs):
        return httpx.Response(200, json=[
            {"key": "OPS", "id": "10001", "name": "Operations", "projectTypeKey": "business"},
            {"key": "PAY", "id": "10002", "name": "Payments", "projectTypeKey": "software"},
        ], request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="jira", provider_type=ProviderType.ITSM, credential_ref="env://JIRA_TOKEN",
        discovery_scope={"base_url": "https://acme.atlassian.net", "email": "bot@acme.com"},
    )
    result = await JiraConnector().discover_resources(connection, _request())
    assert {r.resource_type for r in result.resources} == {"jira_project"}
    assert {r.display_name for r in result.resources} == {"Operations", "Payments"}
    assert all(r.connection_id == connection.id for r in result.resources)


@pytest.mark.asyncio
async def test_jira_knowledge_candidates_returns_resolved_issues_for_human_review(monkeypatch):
    monkeypatch.setenv("JIRA_TOKEN", "tok-123")

    async def request(self, method, url, **kwargs):
        return httpx.Response(200, json={"issues": [
            {"key": "OPS-42", "fields": {"summary": "Fixed checkout timeout", "description": "Root cause was a stale connection pool.", "updated": "2026-08-01", "project": {"key": "OPS"}}},
        ]}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="jira", provider_type=ProviderType.ITSM, credential_ref="env://JIRA_TOKEN",
        discovery_scope={"base_url": "https://acme.atlassian.net", "email": "bot@acme.com"},
    )
    candidates = await JiraConnector().knowledge_candidates(connection)
    assert len(candidates) == 1
    assert candidates[0]["source_ref"] == "jira://OPS-42"
    assert "stale connection pool" in candidates[0]["content"]


# --- ServiceNow --------------------------------------------------------

@pytest.mark.asyncio
async def test_servicenow_discover_resources_maps_assignment_groups(monkeypatch):
    monkeypatch.setenv("SNOW_PASSWORD", "pw")

    async def request(self, method, url, **kwargs):
        return httpx.Response(200, json={"result": [{"sys_id": "grp1", "name": "Network Ops", "description": "NOC"}]}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="servicenow", provider_type=ProviderType.ITSM, credential_ref="env://SNOW_PASSWORD",
        discovery_scope={"base_url": "https://acme.service-now.com", "username": "kaims-integration"},
    )
    result = await ServiceNowConnector().discover_resources(connection, _request())
    assert result.resources[0].resource_type == "servicenow_assignment_group"
    assert result.resources[0].display_name == "Network Ops"


# --- Azure DevOps --------------------------------------------------------

@pytest.mark.asyncio
async def test_azure_devops_validate_connection_uses_pat_as_password(monkeypatch):
    monkeypatch.setenv("ADO_PAT", "pat-abc")
    seen = {}

    async def request(self, method, url, **kwargs):
        seen["auth"] = self.auth
        return httpx.Response(200, json={"value": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="azure_devops", provider_type=ProviderType.ITSM, credential_ref="env://ADO_PAT",
        discovery_scope={"organization": "acme-corp"},
    )
    result = await AzureDevOpsConnector().validate_connection(connection)
    assert result.status == "validated"
    assert seen["auth"] is not None


@pytest.mark.asyncio
async def test_azure_devops_requires_organization():
    connection = _connection(
        connector_id="azure_devops", provider_type=ProviderType.ITSM, credential_ref="env://ADO_PAT",
        discovery_scope={},
    )
    result = await AzureDevOpsConnector().validate_connection(connection)
    assert result.status == "failed"
    assert "organization" in result.message


# --- Prometheus --------------------------------------------------------

@pytest.mark.asyncio
async def test_prometheus_validate_connection_works_without_credentials(monkeypatch):
    async def request(self, method, url, **kwargs):
        assert "authorization" not in self.headers
        return httpx.Response(200, text="Prometheus Server is Healthy.", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="prometheus", provider_type=ProviderType.MONITORING, credential_ref="",
        discovery_scope={"base_url": "http://prometheus:9090"},
    )
    result = await PrometheusConnector().validate_connection(connection)
    assert result.status == "validated"


@pytest.mark.asyncio
async def test_prometheus_discover_resources_maps_active_targets(monkeypatch):
    async def request(self, method, url, **kwargs):
        return httpx.Response(200, json={"data": {"activeTargets": [
            {"labels": {"job": "api-gateway", "instance": "api-gateway:8000"}, "health": "up", "lastScrape": "2026-09-05T00:00:00Z"},
        ]}}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="prometheus", provider_type=ProviderType.MONITORING, credential_ref="",
        discovery_scope={"base_url": "http://prometheus:9090"},
    )
    result = await PrometheusConnector().discover_resources(connection, _request())
    assert result.resources[0].resource_type == "prometheus_target"
    assert result.resources[0].health["status"] == "up"


# --- Grafana --------------------------------------------------------

@pytest.mark.asyncio
async def test_grafana_discover_resources_maps_dashboards(monkeypatch):
    monkeypatch.setenv("GRAFANA_TOKEN", "gtok")

    async def request(self, method, url, **kwargs):
        return httpx.Response(200, json=[{"uid": "d1", "title": "Checkout latency", "folderTitle": "Platform"}], request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="grafana", provider_type=ProviderType.MONITORING, credential_ref="env://GRAFANA_TOKEN",
        discovery_scope={"base_url": "http://grafana:3000"},
    )
    result = await GrafanaConnector().discover_resources(connection, _request())
    assert result.resources[0].display_name == "Checkout latency"


# --- Datadog --------------------------------------------------------

@pytest.mark.asyncio
async def test_datadog_validate_connection_checks_the_validate_endpoint(monkeypatch):
    monkeypatch.setenv("DD_API_KEY", "ddkey")

    async def request(self, method, url, **kwargs):
        return httpx.Response(200, json={"valid": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="datadog", provider_type=ProviderType.MONITORING, credential_ref="env://DD_API_KEY",
        discovery_scope={"site": "datadoghq.com"},
    )
    result = await DatadogConnector().validate_connection(connection)
    assert result.status == "validated"


@pytest.mark.asyncio
async def test_datadog_discover_resources_requires_an_application_key(monkeypatch):
    monkeypatch.setenv("DD_API_KEY", "ddkey")
    connection = _connection(
        connector_id="datadog", provider_type=ProviderType.MONITORING, credential_ref="env://DD_API_KEY",
        discovery_scope={"site": "datadoghq.com"},
    )
    with pytest.raises(Exception, match="app_key_secret_ref"):
        await DatadogConnector().discover_resources(connection, _request())


@pytest.mark.asyncio
async def test_dynatrace_validate_connection_checks_host_entities(monkeypatch):
    monkeypatch.setenv("DYNATRACE_TOKEN", "dt-token")
    seen = {}

    async def request(self, method, url, **kwargs):
        seen["headers"] = dict(self.headers)
        return httpx.Response(200, json={"entities": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="dynatrace", provider_type=ProviderType.MONITORING, credential_ref="env://DYNATRACE_TOKEN",
        discovery_scope={"base_url": "https://abc12345.live.dynatrace.com"},
    )
    result = await DynatraceConnector().validate_connection(connection)
    assert result.status == "validated"
    assert seen["headers"]["authorization"] == "Api-Token dt-token"


@pytest.mark.asyncio
async def test_dynatrace_discover_resources_maps_service_entities(monkeypatch):
    monkeypatch.setenv("DYNATRACE_TOKEN", "dt-token")

    async def request(self, method, url, **kwargs):
        return httpx.Response(200, json={"entities": [
            {"entityId": "SERVICE-123", "displayName": "checkout-api", "properties": {"technologies": ["Python"]}},
        ]}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    connection = _connection(
        connector_id="dynatrace", provider_type=ProviderType.MONITORING, credential_ref="env://DYNATRACE_TOKEN",
        discovery_scope={"base_url": "https://abc12345.live.dynatrace.com"},
    )
    result = await DynatraceConnector().discover_resources(connection, _request())
    assert result.resources[0].resource_type == "dynatrace_service"
    assert result.resources[0].display_name == "checkout-api"


def test_connector_for_dispatches_dynatrace():
    assert isinstance(connector_for(ProviderType.MONITORING, connector_id="dynatrace"), DynatraceConnector)


@pytest.mark.asyncio
async def test_read_only_connectors_refuse_to_execute_actions():
    connector = PrometheusConnector()
    with pytest.raises(NotImplementedError, match="read-only"):
        await connector.execute_action(action={}, idempotency_key="k1")
