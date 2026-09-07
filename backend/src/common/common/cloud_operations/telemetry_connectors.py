from __future__ import annotations

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


class MonitoringConnectorError(RuntimeError):
    pass


def _rid(connector_id: str, project_id: str, kind: str, name: str) -> str:
    return f"{connector_id}://{project_id}/{kind}/{name}"


async def _optional_bearer(connection: CloudConnection) -> dict[str, str]:
    """Most self-hosted Prometheus/Grafana installs sit behind network policy rather than
    a token; only attach a bearer header when the connection actually supplies one."""
    ref = str(connection.credential_ref or "").strip()
    if not ref:
        return {}
    token = await resolve_secret_ref(ref)
    return {"Authorization": f"Bearer {token}"}


class PrometheusConnector(ReadOnlyConnectorMixin):
    """Real Prometheus HTTP API client.

    discovery_scope: {"connector_id": "prometheus", "base_url": "http://prometheus:9090"}
    credential_ref: optional env:// bearer token; leave empty for unauthenticated instances.
    """

    connector_id = "prometheus"

    def list_capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            provider=ProviderType.MONITORING, connector_version="prometheus-http-api-v1",
            resource_types=["prometheus_target"],
            supported_read_operations=["validate_connection", "discover_resources", "get_metrics"],
            supported_write_operations=[], required_permission_scopes=["prometheus.query"],
            risk_classification="low", dry_run_support=True, rollback_support=False,
            validation_support=True, health_status="healthy",
        )

    def _base_url(self, connection: CloudConnection) -> str:
        base_url = str(connection.discovery_scope.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise MonitoringConnectorError("Prometheus connections require discovery_scope.base_url")
        return base_url

    async def validate_connection(self, connection: CloudConnection) -> ConnectionValidationResult:
        try:
            base_url = self._base_url(connection)
            headers = await _optional_bearer(connection)
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
                response = await client.get(f"{base_url}/-/healthy")
            ok = response.status_code == 200
            message = "Prometheus is reachable and healthy." if ok else f"Prometheus responded {response.status_code}: {response.text[:200]}"
        except (MonitoringConnectorError, SecretResolutionError, httpx.HTTPError) as exc:
            ok = False
            message = f"Prometheus connection failed: {exc}"
        return ConnectionValidationResult(
            status="validated" if ok else "failed", connectivity_ok=ok, authentication_ok=ok,
            requested_permissions=["prometheus.query"], granted_permissions=["prometheus.query"] if ok else [],
            missing_permissions=[] if ok else ["prometheus.query"], read_only=True, message=message,
        )

    async def discover_resources(self, connection: CloudConnection, request: DiscoveryRequest) -> DiscoveryResult:
        base_url = self._base_url(connection)
        headers = await _optional_bearer(connection)
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
            response = await client.get(f"{base_url}/api/v1/targets")
            response.raise_for_status()
            payload = response.json()
        active_targets = ((payload.get("data") or {}).get("activeTargets") or [])
        resources = []
        for target in active_targets:
            labels = target.get("labels") or {}
            job = str(labels.get("job") or "unknown")
            instance = str(labels.get("instance") or target.get("scrapeUrl") or "target")
            resources.append(DiscoveredResource(
                id=uuid5(NAMESPACE_URL, _rid("prometheus", request.project_id, "target", f"{job}/{instance}")),
                tenant_id=request.tenant_id, project_id=request.project_id, connection_id=connection.id,
                service_id=request.service_id, environment=request.environment, provider=ProviderType.MONITORING,
                provider_account_id=base_url, region="global",
                provider_resource_id=_rid("prometheus", request.project_id, "target", f"{job}/{instance}"),
                resource_type="prometheus_target", display_name=f"{job} ({instance})",
                owner=connection.connection_owner,
                health={"status": "up" if target.get("health") == "up" else "down", "last_scrape": target.get("lastScrape")},
                tags={"source": "prometheus", "job": job},
            ))
        return DiscoveryResult(
            run_id=uuid5(NAMESPACE_URL, f"discovery:prometheus:{connection.id}"),
            status=DiscoveryStatus.COMPLETED, resources=resources, relationships=[],
            message=f"Discovered {len(resources)} Prometheus scrape target(s).",
        )


class GrafanaConnector(ReadOnlyConnectorMixin):
    """Real Grafana HTTP API client.

    discovery_scope: {"connector_id": "grafana", "base_url": "http://grafana:3000"}
    credential_ref: env:// reference to a Grafana service account token.
    """

    connector_id = "grafana"

    def list_capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            provider=ProviderType.MONITORING, connector_version="grafana-http-api-v1",
            resource_types=["grafana_dashboard"],
            supported_read_operations=["validate_connection", "discover_resources"],
            supported_write_operations=[], required_permission_scopes=["grafana.dashboards.read"],
            risk_classification="low", dry_run_support=True, rollback_support=False,
            validation_support=True, health_status="healthy",
        )

    def _base_url(self, connection: CloudConnection) -> str:
        base_url = str(connection.discovery_scope.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise MonitoringConnectorError("Grafana connections require discovery_scope.base_url")
        return base_url

    async def validate_connection(self, connection: CloudConnection) -> ConnectionValidationResult:
        try:
            base_url = self._base_url(connection)
            token = await resolve_secret_ref(connection.credential_ref)
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"Authorization": f"Bearer {token}"}) as client:
                response = await client.get(f"{base_url}/api/org")
            ok = response.status_code == 200
            message = "Grafana service account token is valid." if ok else f"Grafana responded {response.status_code}: {response.text[:200]}"
        except (MonitoringConnectorError, SecretResolutionError, httpx.HTTPError) as exc:
            ok = False
            message = f"Grafana connection failed: {exc}"
        return ConnectionValidationResult(
            status="validated" if ok else "failed", connectivity_ok=ok, authentication_ok=ok,
            requested_permissions=["grafana.dashboards.read"], granted_permissions=["grafana.dashboards.read"] if ok else [],
            missing_permissions=[] if ok else ["grafana.dashboards.read"], read_only=True, message=message,
        )

    async def discover_resources(self, connection: CloudConnection, request: DiscoveryRequest) -> DiscoveryResult:
        base_url = self._base_url(connection)
        token = await resolve_secret_ref(connection.credential_ref)
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"Authorization": f"Bearer {token}"}) as client:
            response = await client.get(f"{base_url}/api/search", params={"type": "dash-db", "limit": 100})
            response.raise_for_status()
            dashboards = response.json()
        resources = [
            DiscoveredResource(
                id=uuid5(NAMESPACE_URL, _rid("grafana", request.project_id, "dashboard", str(dashboard.get("uid")))),
                tenant_id=request.tenant_id, project_id=request.project_id, connection_id=connection.id,
                service_id=request.service_id, environment=request.environment, provider=ProviderType.MONITORING,
                provider_account_id=base_url, region="global",
                provider_resource_id=_rid("grafana", request.project_id, "dashboard", str(dashboard.get("uid"))),
                resource_type="grafana_dashboard", display_name=str(dashboard.get("title") or "Grafana dashboard"),
                owner=connection.connection_owner,
                configuration={"uid": dashboard.get("uid"), "folder_title": dashboard.get("folderTitle")},
                tags={"source": "grafana"},
            )
            for dashboard in (dashboards if isinstance(dashboards, list) else [])
        ]
        return DiscoveryResult(
            run_id=uuid5(NAMESPACE_URL, f"discovery:grafana:{connection.id}"),
            status=DiscoveryStatus.COMPLETED, resources=resources, relationships=[],
            message=f"Discovered {len(resources)} Grafana dashboard(s).",
        )


class DatadogConnector(ReadOnlyConnectorMixin):
    """Real Datadog HTTP API client.

    discovery_scope: {"connector_id": "datadog", "site": "datadoghq.com", "app_key_secret_ref": "env://DATADOG_APP_KEY"}
    credential_ref: env:// reference to the Datadog API key. Discovering monitors also
    needs an application key, referenced separately since Datadog issues the two keys
    independently and either may need to be rotated on its own.
    """

    connector_id = "datadog"

    def list_capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            provider=ProviderType.MONITORING, connector_version="datadog-api-v1",
            resource_types=["datadog_monitor"],
            supported_read_operations=["validate_connection", "discover_resources", "get_metrics"],
            supported_write_operations=[], required_permission_scopes=["datadog.monitors_read"],
            risk_classification="low", dry_run_support=True, rollback_support=False,
            validation_support=True, health_status="healthy",
        )

    def _site(self, connection: CloudConnection) -> str:
        return str(connection.discovery_scope.get("site") or "datadoghq.com").strip() or "datadoghq.com"

    async def validate_connection(self, connection: CloudConnection) -> ConnectionValidationResult:
        try:
            site = self._site(connection)
            api_key = await resolve_secret_ref(connection.credential_ref)
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"DD-API-KEY": api_key}) as client:
                response = await client.get(f"https://api.{site}/api/v1/validate")
            ok = response.status_code == 200 and bool(response.json().get("valid"))
            message = "Datadog API key is valid." if ok else f"Datadog responded {response.status_code}: {response.text[:200]}"
        except (SecretResolutionError, httpx.HTTPError, ValueError) as exc:
            ok = False
            message = f"Datadog connection failed: {exc}"
        return ConnectionValidationResult(
            status="validated" if ok else "failed", connectivity_ok=ok, authentication_ok=ok,
            requested_permissions=["datadog.monitors_read"], granted_permissions=["datadog.monitors_read"] if ok else [],
            missing_permissions=[] if ok else ["datadog.monitors_read"], read_only=True, message=message,
        )

    async def discover_resources(self, connection: CloudConnection, request: DiscoveryRequest) -> DiscoveryResult:
        site = self._site(connection)
        api_key = await resolve_secret_ref(connection.credential_ref)
        app_key_ref = str(connection.discovery_scope.get("app_key_secret_ref") or "").strip()
        if not app_key_ref:
            raise MonitoringConnectorError("Discovering Datadog monitors requires discovery_scope.app_key_secret_ref")
        app_key = await resolve_secret_ref(app_key_ref)
        headers = {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key}
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
            response = await client.get(f"https://api.{site}/api/v1/monitor")
            response.raise_for_status()
            monitors = response.json()
        resources = [
            DiscoveredResource(
                id=uuid5(NAMESPACE_URL, _rid("datadog", request.project_id, "monitor", str(monitor.get("id")))),
                tenant_id=request.tenant_id, project_id=request.project_id, connection_id=connection.id,
                service_id=request.service_id, environment=request.environment, provider=ProviderType.MONITORING,
                provider_account_id=site, region="global",
                provider_resource_id=_rid("datadog", request.project_id, "monitor", str(monitor.get("id"))),
                resource_type="datadog_monitor", display_name=str(monitor.get("name") or "Datadog monitor"),
                owner=connection.connection_owner,
                health={"overall_state": monitor.get("overall_state")},
                configuration={"type": monitor.get("type"), "query": monitor.get("query")},
                tags={"source": "datadog"},
            )
            for monitor in (monitors if isinstance(monitors, list) else [])
        ]
        return DiscoveryResult(
            run_id=uuid5(NAMESPACE_URL, f"discovery:datadog:{connection.id}"),
            status=DiscoveryStatus.COMPLETED, resources=resources, relationships=[],
            message=f"Discovered {len(resources)} Datadog monitor(s).",
        )


class DynatraceConnector(ReadOnlyConnectorMixin):
    """Real Dynatrace Environment API v2 client.

    discovery_scope: {"connector_id": "dynatrace", "base_url": "https://abc12345.live.dynatrace.com"}
    (Managed clusters use their own https://{cluster}/e/{environment-id} base_url.)
    credential_ref: env:// reference to a Dynatrace API token with entities.read scope.
    """

    connector_id = "dynatrace"

    def list_capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            provider=ProviderType.MONITORING, connector_version="dynatrace-environment-api-v2",
            resource_types=["dynatrace_service"],
            supported_read_operations=["validate_connection", "discover_resources", "get_metrics"],
            supported_write_operations=[], required_permission_scopes=["entities.read"],
            risk_classification="low", dry_run_support=True, rollback_support=False,
            validation_support=True, health_status="healthy",
        )

    def _base_url(self, connection: CloudConnection) -> str:
        base_url = str(connection.discovery_scope.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise MonitoringConnectorError("Dynatrace connections require discovery_scope.base_url")
        return base_url

    async def validate_connection(self, connection: CloudConnection) -> ConnectionValidationResult:
        try:
            base_url = self._base_url(connection)
            token = await resolve_secret_ref(connection.credential_ref)
            headers = {"Authorization": f"Api-Token {token}"}
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
                response = await client.get(f"{base_url}/api/v2/entities", params={"entitySelector": "type(HOST)", "pageSize": 1})
            ok = response.status_code == 200
            message = "Dynatrace API token is valid." if ok else f"Dynatrace responded {response.status_code}: {response.text[:200]}"
        except (MonitoringConnectorError, SecretResolutionError, httpx.HTTPError) as exc:
            ok = False
            message = f"Dynatrace connection failed: {exc}"
        return ConnectionValidationResult(
            status="validated" if ok else "failed", connectivity_ok=ok, authentication_ok=ok,
            requested_permissions=["entities.read"], granted_permissions=["entities.read"] if ok else [],
            missing_permissions=[] if ok else ["entities.read"], read_only=True, message=message,
        )

    async def discover_resources(self, connection: CloudConnection, request: DiscoveryRequest) -> DiscoveryResult:
        base_url = self._base_url(connection)
        token = await resolve_secret_ref(connection.credential_ref)
        headers = {"Authorization": f"Api-Token {token}"}
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
            response = await client.get(
                f"{base_url}/api/v2/entities",
                params={"entitySelector": "type(SERVICE)", "pageSize": 100, "fields": "+properties,+fromRelationships,+toRelationships"},
            )
            response.raise_for_status()
            entities = response.json().get("entities", [])
        resources = [
            DiscoveredResource(
                id=uuid5(NAMESPACE_URL, _rid("dynatrace", request.project_id, "service", str(entity.get("entityId")))),
                tenant_id=request.tenant_id, project_id=request.project_id, connection_id=connection.id,
                service_id=request.service_id, environment=request.environment, provider=ProviderType.MONITORING,
                provider_account_id=base_url, region="global",
                provider_resource_id=_rid("dynatrace", request.project_id, "service", str(entity.get("entityId"))),
                resource_type="dynatrace_service", display_name=str(entity.get("displayName") or "Dynatrace service"),
                owner=connection.connection_owner,
                configuration={"entity_id": entity.get("entityId"), "properties": entity.get("properties")},
                tags={"source": "dynatrace"},
            )
            for entity in entities
        ]
        return DiscoveryResult(
            run_id=uuid5(NAMESPACE_URL, f"discovery:dynatrace:{connection.id}"),
            status=DiscoveryStatus.COMPLETED, resources=resources, relationships=[],
            message=f"Discovered {len(resources)} Dynatrace-monitored service(s).",
        )
