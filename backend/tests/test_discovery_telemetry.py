import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "src" / "discovery-mcp" / "app.py"
SPEC = importlib.util.spec_from_file_location("discovery_mcp_telemetry_app", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_telemetry_project_routes_code_search_to_astronomy_shop(monkeypatch):
    project_root = Path("/workspace/external/telemetry/opentelemetry-demo")
    monkeypatch.setattr(
        MODULE,
        "_project_catalog",
        lambda: {
            "telemetry": {
                "name": "telemetry",
                "aliases": ["astronomy-shop"],
                "code_roots": [str(project_root)],
            }
        },
    )

    roots = MODULE._code_roots({"project": "telemetry", "terms": ["payment"]})

    assert roots == [project_root]


def test_project_resolves_unique_service_catalog_match(monkeypatch, tmp_path):
    kaiops_root = tmp_path / "kaiops"
    telemetry_root = tmp_path / "telemetry"
    (kaiops_root / "api-gateway").mkdir(parents=True)
    telemetry_root.mkdir()
    monkeypatch.setattr(
        MODULE,
        "_project_catalog",
        lambda: {
            "kaiops": {"service_catalog_root": str(kaiops_root)},
            "telemetry": {"service_catalog_root": str(telemetry_root)},
        },
    )

    project_id, project = MODULE._project_for({"service": "api-gateway"})

    assert project_id == "kaiops"
    assert project["service_catalog_root"] == str(kaiops_root)


def test_project_does_not_guess_when_service_matches_multiple_catalogs(monkeypatch, tmp_path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    (first_root / "shared-service").mkdir(parents=True)
    (second_root / "shared-service").mkdir(parents=True)
    monkeypatch.setattr(
        MODULE,
        "_project_catalog",
        lambda: {
            "first": {"service_catalog_root": str(first_root)},
            "second": {"service_catalog_root": str(second_root)},
        },
    )

    assert MODULE._project_for({"service": "shared-service"}) == ("", {})


def test_telemetry_tool_is_published():
    names = {tool["name"] for tool in MODULE.TOOLS}
    assert "telemetry.search" in names


def test_kaiops_project_exposes_internal_prometheus_and_jaeger():
    catalog_path = Path(__file__).parents[1] / "config" / "discovery-projects.json"
    kaiops = json.loads(catalog_path.read_text(encoding="utf-8"))["projects"]["kaiops"]

    assert kaiops["telemetry"]["prometheus_url"] == "http://prometheus:9090"
    assert kaiops["telemetry"]["jaeger_url"] == "http://jaeger:16686"


def test_trace_summary_preserves_causal_diagnostics():
    trace = {
        "traceID": "trace-1",
        "processes": {"p1": {"serviceName": "api-gateway"}, "p2": {"serviceName": "mysql"}},
        "spans": [{
            "spanID": "root", "processID": "p1",
            "operationName": "GET /alerts/{alert_id}/processed-result",
            "duration": 4_200_000,
            "tags": [{"key": "http.status_code", "value": 503}],
            "logs": [],
        }, {
            "spanID": "child", "processID": "p2", "operationName": "SELECT", "duration": 900_000,
            "references": [{"refType": "CHILD_OF", "spanID": "root"}],
            "tags": [{"key": "db.system", "value": "mysql"}], "logs": [],
        }],
    }

    summary = MODULE._trace_evidence_summary(trace, "/alerts/abc/processed-result")

    assert summary["duration_ms"] == 4200.0
    assert summary["http_status_codes"] == [503]
    assert summary["services"] == ["api-gateway", "mysql"]
    assert set(summary["diagnostic_signals"]) == {"http_5xx", "high_latency"}
    assert summary["slowest_spans"][1]["tags"]["db.system"] == "mysql"
    assert summary["dependency_edges"] == [{"upstream": "api-gateway", "downstream": "mysql"}]


def test_jaeger_operation_normalizes_alert_uuid_and_query_string():
    operation = "/alerts/ab4e7d57-e348-48a3-95bd-4ff1fcae6ca4/processed-result?tenant_id=default"

    assert MODULE._jaeger_operation(operation) == "GET /alerts/{alert_id}/processed-result"


@pytest.mark.asyncio
async def test_missing_bound_trace_falls_back_to_incident_scoped_jaeger_search(monkeypatch):
    trace = {
        "traceID": "fallback-trace",
        "processes": {"p1": {"serviceName": "api-gateway"}},
        "spans": [{
            "spanID": "root", "processID": "p1",
            "operationName": "GET /alerts/{alert_id}/processed-result",
            "duration": 2_500_000, "startTime": 1_788_315_300_000_000,
            "tags": [], "logs": [],
        }],
    }

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            self.calls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            self.calls.append((url, params))
            if url.endswith("/api/traces/missing-correlation-id"):
                return Response(404, {})
            if url.endswith("/api/traces"):
                if params and params.get("operation"):
                    return Response(200, {"data": []})
                return Response(200, {"data": [trace]})
            return Response(200, {"data": {"result": []}})

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "kaiops": {
            "aliases": ["kaiops"],
            "telemetry": {
                "prometheus_url": "http://prometheus:9090",
                "jaeger_url": "http://jaeger:16686",
            },
        },
    })

    result = await MODULE._search_traces({
        "project": "kaiops", "service": "api-gateway",
        "trace_id": "missing-correlation-id",
        "operation": "/alerts/abc/processed-result?tenant_id=default",
        "start_time": "2026-09-02T02:14:00Z", "end_time": "2026-09-02T02:34:00Z",
        "limit": 5,
    })

    assert result["result_count"] == 1
    assert result["evidence"][0]["trace_id"] == "fallback-trace"
    jaeger = next(source for source in result["sources"] if source["source"] == "jaeger")
    assert jaeger["bound_trace_fallback"] is True
    assert jaeger["operation_filter_fallback"] is True
    assert result["evidence_gap"] == ""

    unbound_result = await MODULE._search_traces({
        "project": "kaiops", "service": "api-gateway",
        "operation": "/alerts/abc/processed-result?tenant_id=default",
        "start_time": "2026-09-02T02:14:00Z", "end_time": "2026-09-02T02:34:00Z",
        "limit": 5,
    })
    assert unbound_result["result_count"] == 1
    unbound_jaeger = next(source for source in unbound_result["sources"] if source["source"] == "jaeger")
    assert unbound_jaeger["operation_filter_fallback"] is True


@pytest.mark.asyncio
async def test_trace_evidence_survives_a_busy_prometheus_series(monkeypatch):
    """Prometheus is queried before Jaeger and, for any actively-scraped
    service, routinely returns at least `limit` series on its own. The final
    evidence list used to be re-sliced to `limit` after merging every source,
    so a busy Prometheus response alone filled the whole quota and silently
    dropped every trace (and log/opensearch) result queried afterward - even
    though Jaeger genuinely had a match. This must not regress."""
    trace = {
        "traceID": "busy-trace",
        "processes": {"p1": {"serviceName": "api-gateway"}},
        "spans": [{
            "spanID": "root", "processID": "p1", "operationName": "GET /healthz",
            "duration": 1_200, "startTime": 1_788_315_300_000_000, "tags": [], "logs": [],
        }],
    }
    prometheus_series = [
        {"metric": {"__name__": "up", "service": "api-gateway", "instance": f"api-gateway-{i}"}, "value": [1788315300, "1"]}
        for i in range(20)  # comfortably more than the default limit of 8
    ]

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            if url.endswith("/api/traces"):
                return Response(200, {"data": [trace]})
            return Response(200, {"data": {"result": prometheus_series}})

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "kaiops": {
            "aliases": ["kaiops"],
            "telemetry": {"prometheus_url": "http://prometheus:9090", "jaeger_url": "http://jaeger:16686"},
        },
    })

    traces_result = await MODULE._search_traces({"project": "kaiops", "service": "api-gateway"})
    assert traces_result["result_count"] == 1
    assert traces_result["evidence"][0]["trace_id"] == "busy-trace"

    telemetry_result = await MODULE._search_telemetry({"project": "kaiops", "service": "api-gateway"})
    sources_in_evidence = {row["source"] for row in telemetry_result["evidence"]}
    assert "trace" in sources_in_evidence
    assert "metric" in sources_in_evidence


@pytest.mark.asyncio
async def test_platform_wide_telemetry_target_does_not_search_for_a_literal_series(monkeypatch):
    """A platform-level incident (target == the project's own alias, e.g.
    "kaiops-platform") has no single service_name series to match. Querying
    for one literally returns zero rows even though the platform's own
    metrics are healthy and being scraped -- this is exactly what made
    telemetry evidence silently vanish for platform-wide incidents.
    """
    seen_queries: list[str] = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            seen_queries.append(params.get("query", ""))
            return Response({"data": {"result": [{"metric": {"__name__": "up"}, "value": [0, "1"]}]}})

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "kaiops": {
            "name": "kaiops",
            "display_name": "KaiOps Platform",
            "platform": True,
            "aliases": ["kaiops-platform", "kaiops-core"],
            "telemetry": {"prometheus_url": "http://prometheus:9090"},
        },
    })

    result = await MODULE._search_telemetry({"project": "kaiops-platform", "service": "kaiops-platform"})

    assert seen_queries == ["up"]
    prometheus_source = next(source for source in result["sources"] if source["source"] == "prometheus")
    assert prometheus_source["result_count"] == 1


@pytest.mark.asyncio
async def test_telemetry_matches_both_service_and_service_name_labels(monkeypatch):
    """This platform's own Prometheus-native metrics (fault-lab, most
    kaiops_* series) label the service with "service", while OTel-instrumented
    services use "service_name". Querying only one convention silently
    dropped evidence for whichever half of the platform used the other one.
    """
    seen_queries: list[str] = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            seen_queries.append(params.get("query", ""))
            return Response({"data": {"result": [{"metric": {"service": "checkout-api"}, "value": [0, "1"]}]}})

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "checkout-api": {
            "name": "checkout-api",
            "aliases": ["checkout-api"],
            "telemetry": {"prometheus_url": "http://prometheus:9090"},
        },
    })

    result = await MODULE._search_telemetry({"project": "checkout-api", "service": "checkout-api"})

    assert seen_queries == ['{service="checkout-api"} or {service_name="checkout-api"}']
    prometheus_source = next(source for source in result["sources"] if source["source"] == "prometheus")
    assert prometheus_source["result_count"] == 1


@pytest.mark.asyncio
async def test_platform_wide_topology_target_returns_all_containers(monkeypatch):
    """The same platform-wide identity applies to topology/dependency search:
    no container is literally named after the umbrella project, so the old
    substring match against a hardcoded "kaiops" left every container
    filtered out -- in any checkout whose actual Compose project name isn't
    literally "kaiops" (this one is "kaims"), dependency evidence was always
    empty regardless of real container health.
    """
    containers = [
        {
            "Names": ["/kaims-remediation-engine-1"],
            "Labels": {
                "com.docker.compose.project": "kaims",
                "com.docker.compose.service": "remediation-engine",
            },
            "State": "running",
            "Status": "Up 5 minutes (healthy)",
            "NetworkSettings": {"Networks": {"kaims_default": {}}},
        },
    ]

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            return Response(containers)

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "kaiops": {
            "name": "kaiops",
            "display_name": "KaiOps Platform",
            "platform": True,
            "aliases": ["kaiops-platform", "kaiops-core"],
        },
    })

    result = await MODULE._search_runtime_topology({"project": "kaiops-platform"}, health_only=False)

    assert result["result_count"] == 1
    assert result["evidence"][0]["service"] == "remediation-engine"


@pytest.mark.asyncio
async def test_platform_wide_target_passed_as_both_project_and_service_still_returns_all_containers(monkeypatch):
    """Reproduces a real live regression found after the fix above: a
    platform-wide incident's context-agent call passes the same identity as
    both project and service (there is no more specific service to name).
    The project-level exemption alone let the service-level filter silently
    filter the result straight back down to zero -- dependency evidence for
    a live "kaiops-platform" incident read 0 despite the earlier fix.
    """
    containers = [
        {
            "Names": ["/kaims-remediation-engine-1"],
            "Labels": {
                "com.docker.compose.project": "kaims",
                "com.docker.compose.service": "remediation-engine",
            },
            "State": "running",
            "Status": "Up 5 minutes (healthy)",
            "NetworkSettings": {"Networks": {"kaims_default": {}}},
        },
        {
            "Names": ["/kaims-api-gateway-1"],
            "Labels": {
                "com.docker.compose.project": "kaims",
                "com.docker.compose.service": "api-gateway",
            },
            "State": "running",
            "Status": "Up 5 minutes (healthy)",
            "NetworkSettings": {"Networks": {"kaims_default": {}}},
        },
    ]

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            return Response(containers)

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "kaiops": {
            "name": "kaiops",
            "display_name": "KaiOps Platform",
            "platform": True,
            "aliases": ["kaiops-platform", "kaiops-core"],
        },
    })

    result = await MODULE._search_runtime_topology(
        {"project": "kaiops-platform", "service": "kaiops-platform"}, health_only=True,
    )

    assert result["result_count"] == 2


@pytest.mark.asyncio
async def test_service_still_narrows_within_a_platform_wide_project(monkeypatch):
    """project="kaiops" (platform-wide) combined with service="api-gateway"
    must return only api-gateway, not every container with the service
    argument silently dropped because a platform-wide project matched first.
    """
    containers = [
        {
            "Names": ["/kaims-api-gateway-1"],
            "Labels": {
                "com.docker.compose.project": "kaims",
                "com.docker.compose.service": "api-gateway",
            },
            "State": "running",
            "Status": "Up 5 minutes (healthy)",
            "NetworkSettings": {"Networks": {"kaims_default": {}}},
        },
        {
            "Names": ["/kaims-orchestrator-1"],
            "Labels": {
                "com.docker.compose.project": "kaims",
                "com.docker.compose.service": "orchestrator",
            },
            "State": "running",
            "Status": "Up 5 minutes",
            "NetworkSettings": {"Networks": {"kaims_default": {}}},
        },
    ]

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            return Response(containers)

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "kaiops": {
            "name": "kaiops",
            "display_name": "KaiOps Platform",
            "platform": True,
            "aliases": ["kaiops-platform", "kaiops-core"],
        },
    })

    result = await MODULE._search_runtime_topology(
        {"project": "kaiops", "service": "api-gateway"}, health_only=False,
    )

    assert result["result_count"] == 1
    assert result["evidence"][0]["service"] == "api-gateway"


def test_onboarded_application_named_after_itself_is_not_platform_wide():
    """A single-service onboarded app whose project entry is named after
    itself (the normal case) must never be mistaken for the umbrella
    platform -- only an entry explicitly marked "platform": true qualifies.
    """
    project = {"name": "checkout-api", "aliases": ["checkout-api"]}

    assert MODULE._is_platform_wide_target("checkout-api", "checkout-api", project) is False


@pytest.mark.asyncio
async def test_traces_search_still_queries_the_shared_jaeger_for_a_service_no_project_ever_matched(monkeypatch):
    """Regression: a service with no onboarded/curated project entry (true
    for every fault-lab scenario service except "api-gateway", which happens
    to also resolve via the code-directory match) used to get an empty
    `telemetry` dict and therefore skip Jaeger entirely - `result_count: 0`
    regardless of whether Jaeger actually held real trace data for that
    service. This deployment has exactly one shared Jaeger/Prometheus that
    every service exports to whether or not it is formally onboarded, so an
    unmatched project must still fall back to querying it - unlike code
    search, which correctly stays empty for an unmatched project to avoid
    citing the wrong application's source."""
    trace = {
        "traceID": "payments-trace",
        "processes": {"p1": {"serviceName": "payments-api"}},
        "spans": [{
            "traceID": "payments-trace", "spanID": "s1", "processID": "p1",
            "operationName": "GET /workload/payments-api", "startTime": 1, "duration": 3_200_000,
            "tags": [{"key": "http.status_code", "value": 504}], "references": [], "logs": [],
        }],
    }

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None):
            if url.endswith("/api/traces"):
                return Response({"data": [trace]})
            return Response({"data": {"result": []}})

    monkeypatch.setattr(MODULE.httpx, "AsyncClient", Client)
    # No entry here matches "payments-api" by alias or service-directory --
    # `_project_for` returns ("", {}), exactly the unmatched case.
    monkeypatch.setattr(MODULE, "_project_catalog", lambda: {
        "kaiops": {"name": "kaiops", "aliases": ["kaiops-platform"], "telemetry": {}},
    })

    result = await MODULE._search_traces({"service": "payments-api", "limit": 5})

    assert result["result_count"] == 1
    assert result["evidence"][0]["trace_id"] == "payments-trace"
