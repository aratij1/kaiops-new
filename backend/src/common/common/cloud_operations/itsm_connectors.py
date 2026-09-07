from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx

from common.cloud_operations.models import (
    CapabilityManifest,
    CloudConnection,
    ConnectionValidationResult,
    DiscoveredResource,
    DiscoveryRequest,
    DiscoveryResult,
    DiscoveryStatus,
    ProviderType,
)
from common.cloud_operations.secret_refs import SecretResolutionError, resolve_secret_ref
from common.cloud_operations.read_only_connector import ReadOnlyConnectorMixin

_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


class ItsmConnectorError(RuntimeError):
    pass


def _rid(connector_id: str, project_id: str, kind: str, name: str) -> str:
    return f"{connector_id}://{project_id}/{kind}/{name}"


class JiraConnector(ReadOnlyConnectorMixin):
    """Real Jira Cloud/Server REST client, scoped to one connection's discovery_scope.

    discovery_scope: {"connector_id": "jira", "base_url": "https://acme.atlassian.net", "email": "bot@acme.com"}
    credential_ref: env:// reference to a Jira API token (Cloud) or password (Server/DC).
    """

    connector_id = "jira"

    def list_capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            provider=ProviderType.ITSM, connector_version="jira-rest-v2",
            resource_types=["jira_project"],
            supported_read_operations=["validate_connection", "discover_resources", "get_changes"],
            supported_write_operations=[],
            required_permission_scopes=["jira.browse_projects"],
            risk_classification="low", dry_run_support=True, rollback_support=False,
            validation_support=True, health_status="healthy",
        )

    def _config(self, connection: CloudConnection) -> tuple[str, str]:
        base_url = str(connection.discovery_scope.get("base_url") or "").strip().rstrip("/")
        email = str(connection.discovery_scope.get("email") or "").strip()
        if not base_url or not email:
            raise ItsmConnectorError("Jira connections require discovery_scope.base_url and discovery_scope.email")
        return base_url, email

    async def validate_connection(self, connection: CloudConnection) -> ConnectionValidationResult:
        try:
            base_url, email = self._config(connection)
            token = await resolve_secret_ref(connection.credential_ref)
            async with httpx.AsyncClient(timeout=_TIMEOUT, auth=(email, token)) as client:
                response = await client.get(f"{base_url}/rest/api/2/myself")
            ok = response.status_code == 200
            message = "Jira credentials are valid." if ok else f"Jira responded {response.status_code}: {response.text[:200]}"
        except (ItsmConnectorError, SecretResolutionError, httpx.HTTPError) as exc:
            ok = False
            message = f"Jira connection failed: {exc}"
        return ConnectionValidationResult(
            status="validated" if ok else "failed", connectivity_ok=ok, authentication_ok=ok,
            requested_permissions=["jira.browse_projects"], granted_permissions=["jira.browse_projects"] if ok else [],
            missing_permissions=[] if ok else ["jira.browse_projects"], read_only=True, message=message,
        )

    async def discover_resources(self, connection: CloudConnection, request: DiscoveryRequest) -> DiscoveryResult:
        base_url, email = self._config(connection)
        token = await resolve_secret_ref(connection.credential_ref)
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=(email, token)) as client:
            response = await client.get(f"{base_url}/rest/api/2/project")
            response.raise_for_status()
            projects = response.json()
        resources = [
            DiscoveredResource(
                id=uuid5(NAMESPACE_URL, _rid("jira", request.project_id, "project", str(project.get("key") or project.get("id")))),
                tenant_id=request.tenant_id, project_id=request.project_id, connection_id=connection.id,
                service_id=request.service_id, environment=request.environment, provider=ProviderType.ITSM,
                provider_account_id=base_url, region="global",
                provider_resource_id=_rid("jira", request.project_id, "project", str(project.get("key") or project.get("id"))),
                resource_type="jira_project", display_name=str(project.get("name") or project.get("key") or "Jira project"),
                owner=connection.connection_owner,
                configuration={"key": project.get("key"), "id": project.get("id"), "project_type": project.get("projectTypeKey")},
                tags={"source": "jira"},
            )
            for project in (projects if isinstance(projects, list) else [])
        ]
        return DiscoveryResult(
            run_id=uuid5(NAMESPACE_URL, f"discovery:jira:{connection.id}"),
            status=DiscoveryStatus.COMPLETED, resources=resources, relationships=[],
            message=f"Discovered {len(resources)} Jira project(s).",
        )

    async def knowledge_candidates(self, connection: CloudConnection, *, limit: int = 20) -> list[dict[str, Any]]:
        """Resolved issues, offered as human-reviewable knowledge base candidates (not auto-ingested)."""
        base_url, email = self._config(connection)
        token = await resolve_secret_ref(connection.credential_ref)
        params = {
            "jql": "resolution is not EMPTY ORDER BY updated DESC",
            "maxResults": limit,
            "fields": "summary,description,resolution,updated,project",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=(email, token)) as client:
            response = await client.get(f"{base_url}/rest/api/2/search", params=params)
            response.raise_for_status()
            payload = response.json()
        candidates = []
        for issue in payload.get("issues", []):
            fields = issue.get("fields", {}) or {}
            key = issue.get("key", "")
            candidates.append({
                "source_ref": f"jira://{key}",
                "title": f"{key}: {fields.get('summary', '')}".strip(": "),
                "content": str(fields.get("description") or fields.get("summary") or ""),
                "metadata": {"connector_id": "jira", "issue_key": key, "updated": fields.get("updated"),
                             "project": (fields.get("project") or {}).get("key")},
            })
        return candidates


class ServiceNowConnector(ReadOnlyConnectorMixin):
    """Real ServiceNow Table API client.

    discovery_scope: {"connector_id": "servicenow", "base_url": "https://acme.service-now.com", "username": "kaims-integration"}
    credential_ref: env:// reference to the account's password or API key.
    """

    connector_id = "servicenow"

    def list_capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            provider=ProviderType.ITSM, connector_version="servicenow-table-api-v1",
            resource_types=["servicenow_assignment_group"],
            supported_read_operations=["validate_connection", "discover_resources", "get_changes"],
            supported_write_operations=[], required_permission_scopes=["servicenow.table.read"],
            risk_classification="low", dry_run_support=True, rollback_support=False,
            validation_support=True, health_status="healthy",
        )

    def _config(self, connection: CloudConnection) -> tuple[str, str]:
        base_url = str(connection.discovery_scope.get("base_url") or "").strip().rstrip("/")
        username = str(connection.discovery_scope.get("username") or "").strip()
        if not base_url or not username:
            raise ItsmConnectorError("ServiceNow connections require discovery_scope.base_url and discovery_scope.username")
        return base_url, username

    async def validate_connection(self, connection: CloudConnection) -> ConnectionValidationResult:
        try:
            base_url, username = self._config(connection)
            password = await resolve_secret_ref(connection.credential_ref)
            async with httpx.AsyncClient(timeout=_TIMEOUT, auth=(username, password)) as client:
                response = await client.get(f"{base_url}/api/now/table/sys_user", params={"sysparm_limit": 1})
            ok = response.status_code == 200
            message = "ServiceNow credentials are valid." if ok else f"ServiceNow responded {response.status_code}: {response.text[:200]}"
        except (ItsmConnectorError, SecretResolutionError, httpx.HTTPError) as exc:
            ok = False
            message = f"ServiceNow connection failed: {exc}"
        return ConnectionValidationResult(
            status="validated" if ok else "failed", connectivity_ok=ok, authentication_ok=ok,
            requested_permissions=["servicenow.table.read"], granted_permissions=["servicenow.table.read"] if ok else [],
            missing_permissions=[] if ok else ["servicenow.table.read"], read_only=True, message=message,
        )

    async def discover_resources(self, connection: CloudConnection, request: DiscoveryRequest) -> DiscoveryResult:
        base_url, username = self._config(connection)
        password = await resolve_secret_ref(connection.credential_ref)
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=(username, password)) as client:
            response = await client.get(f"{base_url}/api/now/table/sys_user_group", params={"sysparm_limit": 50, "sysparm_query": "active=true"})
            response.raise_for_status()
            groups = response.json().get("result", [])
        resources = [
            DiscoveredResource(
                id=uuid5(NAMESPACE_URL, _rid("servicenow", request.project_id, "assignment_group", str(group.get("sys_id")))),
                tenant_id=request.tenant_id, project_id=request.project_id, connection_id=connection.id,
                service_id=request.service_id, environment=request.environment, provider=ProviderType.ITSM,
                provider_account_id=base_url, region="global",
                provider_resource_id=_rid("servicenow", request.project_id, "assignment_group", str(group.get("sys_id"))),
                resource_type="servicenow_assignment_group", display_name=str(group.get("name") or "ServiceNow group"),
                owner=connection.connection_owner,
                configuration={"sys_id": group.get("sys_id"), "description": group.get("description")},
                tags={"source": "servicenow"},
            )
            for group in groups
        ]
        return DiscoveryResult(
            run_id=uuid5(NAMESPACE_URL, f"discovery:servicenow:{connection.id}"),
            status=DiscoveryStatus.COMPLETED, resources=resources, relationships=[],
            message=f"Discovered {len(resources)} ServiceNow assignment group(s).",
        )

    async def knowledge_candidates(self, connection: CloudConnection, *, limit: int = 20) -> list[dict[str, Any]]:
        base_url, username = self._config(connection)
        password = await resolve_secret_ref(connection.credential_ref)
        params = {"sysparm_limit": limit, "sysparm_query": "workflow_state=published^ORDERBYDESCsys_updated_on"}
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=(username, password)) as client:
            response = await client.get(f"{base_url}/api/now/table/kb_knowledge", params=params)
            response.raise_for_status()
            articles = response.json().get("result", [])
        return [
            {
                "source_ref": f"servicenow://kb/{article.get('sys_id')}",
                "title": str(article.get("short_description") or article.get("number") or "ServiceNow knowledge article"),
                "content": str(article.get("text") or ""),
                "metadata": {"connector_id": "servicenow", "number": article.get("number"), "updated": article.get("sys_updated_on")},
            }
            for article in articles
        ]


class AzureDevOpsConnector(ReadOnlyConnectorMixin):
    """Real Azure DevOps Services REST client, authenticated with a personal access token (PAT).

    discovery_scope: {"connector_id": "azure_devops", "organization": "acme-corp"}
    credential_ref: env:// reference to the PAT.
    """

    connector_id = "azure_devops"
    _API_VERSION = "7.1-preview.4"

    def list_capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            provider=ProviderType.ITSM, connector_version="azure-devops-rest-v7",
            resource_types=["azure_devops_project"],
            supported_read_operations=["validate_connection", "discover_resources", "get_changes"],
            supported_write_operations=[], required_permission_scopes=["azure_devops.project.read"],
            risk_classification="low", dry_run_support=True, rollback_support=False,
            validation_support=True, health_status="healthy",
        )

    def _org(self, connection: CloudConnection) -> str:
        organization = str(connection.discovery_scope.get("organization") or "").strip()
        if not organization:
            raise ItsmConnectorError("Azure DevOps connections require discovery_scope.organization")
        return organization

    async def validate_connection(self, connection: CloudConnection) -> ConnectionValidationResult:
        try:
            organization = self._org(connection)
            pat = await resolve_secret_ref(connection.credential_ref)
            async with httpx.AsyncClient(timeout=_TIMEOUT, auth=("", pat)) as client:
                response = await client.get(
                    f"https://dev.azure.com/{organization}/_apis/projects",
                    params={"api-version": self._API_VERSION},
                )
            ok = response.status_code == 200
            message = "Azure DevOps PAT is valid." if ok else f"Azure DevOps responded {response.status_code}: {response.text[:200]}"
        except (ItsmConnectorError, SecretResolutionError, httpx.HTTPError) as exc:
            ok = False
            message = f"Azure DevOps connection failed: {exc}"
        return ConnectionValidationResult(
            status="validated" if ok else "failed", connectivity_ok=ok, authentication_ok=ok,
            requested_permissions=["azure_devops.project.read"], granted_permissions=["azure_devops.project.read"] if ok else [],
            missing_permissions=[] if ok else ["azure_devops.project.read"], read_only=True, message=message,
        )

    async def discover_resources(self, connection: CloudConnection, request: DiscoveryRequest) -> DiscoveryResult:
        organization = self._org(connection)
        pat = await resolve_secret_ref(connection.credential_ref)
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=("", pat)) as client:
            response = await client.get(
                f"https://dev.azure.com/{organization}/_apis/projects",
                params={"api-version": self._API_VERSION},
            )
            response.raise_for_status()
            projects = response.json().get("value", [])
        resources = [
            DiscoveredResource(
                id=uuid5(NAMESPACE_URL, _rid("azure_devops", request.project_id, "project", str(project.get("id")))),
                tenant_id=request.tenant_id, project_id=request.project_id, connection_id=connection.id,
                service_id=request.service_id, environment=request.environment, provider=ProviderType.ITSM,
                provider_account_id=organization, region="global",
                provider_resource_id=_rid("azure_devops", request.project_id, "project", str(project.get("id"))),
                resource_type="azure_devops_project", display_name=str(project.get("name") or "Azure DevOps project"),
                owner=connection.connection_owner,
                configuration={"id": project.get("id"), "state": project.get("state")},
                tags={"source": "azure_devops"},
            )
            for project in projects
        ]
        return DiscoveryResult(
            run_id=uuid5(NAMESPACE_URL, f"discovery:azure_devops:{connection.id}"),
            status=DiscoveryStatus.COMPLETED, resources=resources, relationships=[],
            message=f"Discovered {len(resources)} Azure DevOps project(s).",
        )

    async def knowledge_candidates(self, connection: CloudConnection, *, limit: int = 20) -> list[dict[str, Any]]:
        """Closed work items across the organization's projects, as knowledge base candidates."""
        organization = self._org(connection)
        pat = await resolve_secret_ref(connection.credential_ref)
        wiql = {"query": "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.State] = 'Closed' ORDER BY [System.ChangedDate] DESC"}
        async with httpx.AsyncClient(timeout=_TIMEOUT, auth=("", pat)) as client:
            search = await client.post(
                f"https://dev.azure.com/{organization}/_apis/wit/wiql",
                params={"api-version": self._API_VERSION}, json=wiql,
            )
            search.raise_for_status()
            ids = [str(item["id"]) for item in search.json().get("workItems", [])[:limit]]
            if not ids:
                return []
            details = await client.get(
                f"https://dev.azure.com/{organization}/_apis/wit/workitems",
                params={"ids": ",".join(ids), "api-version": self._API_VERSION},
            )
            details.raise_for_status()
            items = details.json().get("value", [])
        return [
            {
                "source_ref": f"azure_devops://workitem/{item.get('id')}",
                "title": str((item.get("fields") or {}).get("System.Title") or f"Work item {item.get('id')}"),
                "content": str((item.get("fields") or {}).get("System.Description") or ""),
                "metadata": {"connector_id": "azure_devops", "work_item_id": item.get("id")},
            }
            for item in items
        ]
