"""Bounded normalized telemetry connector; server-owned endpoints, no remote model calls."""
import asyncio
import hashlib
import json
import math
from urllib.parse import unquote, urlsplit
from datetime import datetime, timezone
import httpx
from .handoff import encode
from .incidents import instant
from .native_telemetry import native_request, decode_native


class TelemetryCollector:
    def __init__(self, endpoints, *, transport=None, timeout=8, max_bytes=2097152, max_records=2000):
        self.endpoints, self.transport, self.timeout = endpoints, transport, timeout
        self.max_bytes, self.max_records = max_bytes, max_records

    async def collect(self, config, request):
        sources = config.get("telemetry_sources", [])
        semaphore = asyncio.Semaphore(4)
        async def one(source):
            async with semaphore:
                outcome = {"source_id": source, "status": "not_configured", "accepted": 0, "rejected": 0}
                endpoint = self.endpoints.get(source)
                if endpoint is None: return outcome, []
                if endpoint.get("fixed_service") and endpoint["fixed_service"] != request["service"]:
                    outcome.update(status="not_applicable",reason="source_scoped_to_another_service")
                    return outcome, []
                try:
                    url, params = native_request(endpoint, request, self.max_records)
                    async with asyncio.timeout(self.timeout):
                        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
                            async with client.stream("GET", url, params=params,
                                headers=endpoint.get("headers", {})) as response:
                                response.raise_for_status()
                                chunks = bytearray()
                                async for chunk in response.aiter_bytes():
                                    chunks.extend(chunk)
                                    if len(chunks) > self.max_bytes: raise ValueError("response_size_limit")
                    payload = json.loads(chunks)
                    scoped_endpoint=dict(endpoint)
                    dependencies=[s for s in endpoint.get("dependency_services",{}).get(request["service"],[]) if s in config.get("services",[])]
                    scoped_endpoint["dependency_services"]={request["service"]:dependencies}
                    records, rejected, warnings = decode_native(payload, scoped_endpoint, source, request, self.max_records)
                    outcome["rejected"] = rejected
                    if warnings: outcome["warnings"] = warnings
                    if not isinstance(records, list) or len(records) > self.max_records:
                        raise ValueError("record_limit_or_invalid_shape")
                    accepted = []
                    for record in records:
                        try:
                            validation_request=request
                            if endpoint.get("type")=="jaeger" and record.get("service") in dependencies:
                                validation_request={**request,"service":record["service"]}
                            accepted.append(self.validate(record, source, validation_request))
                        except (ValueError, KeyError, TypeError, AttributeError): outcome["rejected"] += 1
                    # Stable deduplication avoids inflating evidence counts on repeated samples.
                    accepted = list({item["evidence_id"]: item for item in accepted}.values())
                    outcome.update(status="partial" if outcome["rejected"] or warnings else ("collected" if accepted else "no_matches"),
                                   accepted=len(accepted))
                    return outcome, accepted
                except (TimeoutError, httpx.TimeoutException): outcome.update(status="timed_out", reason="source_timeout")
                except httpx.HTTPStatusError as error:
                    outcome.update(status="failed", reason="http_status", http_status=error.response.status_code)
                except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
                    outcome.update(status="failed", reason="invalid_or_unavailable_source")
                return outcome, []
        results = await asyncio.gather(*(one(source) for source in sources))
        return {"source_outcomes": [result[0] for result in results],
                "records": [record for result in results for record in result[1]],
                "window": request, "collected_at": datetime.now(timezone.utc).isoformat()}

    def validate(self, record, source, request):
        if not isinstance(record, dict) or record["service"] != request["service"]:
            raise ValueError("Wrong service")
        timestamp = instant(record["observed_at"])
        if not instant(request["window_start"]) <= timestamp <= instant(request["window_end"]):
            raise ValueError("Outside incident window")
        uri = record["source_uri"]
        if not isinstance(uri, str) or not uri: raise ValueError("Missing operational source")
        normalized = unquote(uri).replace("\\", "/").lower()
        if any(part in normalized for part in ("landing/", "ingested_alerts/", "document://", "alert://")):
            raise ValueError("Not operational evidence")
        kind = record["kind"]
        if kind not in ("metric", "log", "trace"): raise ValueError("Unknown evidence kind")
        if urlsplit(normalized).scheme not in (kind, "http", "https"):
            raise ValueError("Unsupported operational source URI")
        result = {"source_id": source, "service": record["service"], "kind": kind,
                  "source_uri": uri, "observed_at": timestamp.isoformat()}
        if "series_labels" in record:
            labels = record["series_labels"]
            if not isinstance(labels, dict) or len(labels)>128 or any(
                not isinstance(k, str) or not isinstance(v, str) or len(k)>256 or len(v)>4096
                for k, v in labels.items()): raise ValueError("Invalid series labels")
            result["series_labels"] = labels
        if kind == "metric":
            value = record["value"]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError("Invalid metric value")
            metric = record["metric"]
            if metric not in ("error_rate_ratio", "latency_p99_ms", "request_count", "sse_connections") or value < 0:
                raise ValueError("Unsupported metric")
            if metric == "error_rate_ratio" and value > 1: raise ValueError("Invalid error ratio")
            result.update(metric=metric, value=value)
        elif kind == "trace":
            for name in ("trace_id", "span_id"):
                if not isinstance(record[name], str) or not record[name] or len(record[name]) > 128:
                    raise ValueError("Invalid span identity")
            for name in ("parent_span_id", "peer_service"):
                value = record.get(name)
                if value is not None and (not isinstance(value, str) or not value or len(value)>128):
                    raise ValueError("Invalid trace relationship")
            if "duration_ms" in record:
                duration=record["duration_ms"]
                if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<0:
                    raise ValueError("Invalid span duration")
                result["duration_ms"]=duration
            if "operation" in record:
                if not isinstance(record["operation"],str) or len(record["operation"])>1024: raise ValueError("Invalid operation")
                result["operation"]=record["operation"]
            for key,lower,upper in [("http_status_code",100,599),("rpc_status_code",0,16)]:
                if key in record:
                    value=record[key]
                    if isinstance(value,bool) or not isinstance(value,int) or not lower<=value<=upper:
                        raise ValueError("Invalid protocol status")
                    result[key]=value
            if "error_types" in record:
                types=record["error_types"]
                if not isinstance(types,list) or len(types)>5 or any(not isinstance(t,str) or len(t)>256 for t in types):
                    raise ValueError("Invalid exception types")
                result["error_types"]=types
            result.update(trace_id=record["trace_id"], span_id=record["span_id"],
                parent_span_id=record.get("parent_span_id"), peer_service=record.get("peer_service"),
                error=record.get("error") is True)
        else:
            message = record["message"]
            if not isinstance(message, str) or len(message) > 8192: raise ValueError("Invalid log message")
            result["message"] = message
        result["evidence_id"] = hashlib.sha256(encode(result).encode()).hexdigest()
        return result


def assess(evidence, *, request=None, documents=()):
    request = request or evidence.get("window", {})
    records = evidence["records"]
    metrics = [r for r in records if r["kind"] == "metric"]
    errors = [r for r in metrics if r["metric"] == "error_rate_ratio" and r["value"] > 0]
    # A measured error ratio establishes observed service errors, not affected users/revenue.
    impact = {"status": "observed_service_errors" if errors else "not_established",
        "evidence_ids": [r["evidence_id"] for r in errors],
        "measurements": [{"metric": r["metric"], "value": r["value"], "observed_at": r["observed_at"],
                          "evidence_id": r["evidence_id"]} for r in metrics],
        "customer_impact": "not_established", "business_impact": "not_established"}
    sse = [r for r in metrics if r["metric"] == "sse_connections"]
    observations = []
    next_checks = []
    if sse:
        zero = all(r["value"] == 0 for r in sse)
        observations.append({"finding":"All collected SSE connection samples are zero." if zero else "Collected SSE samples include connected clients.",
            "evidence_ids":[r["evidence_id"] for r in sse],
            "limitation":"Connection counts describe connected clients, not endpoint availability. Sampling gaps and uncollected instances remain unknown."})
        next_checks = ["Establish whether any clients were expected to maintain an SSE connection during this window.",
            "Check authenticated client connection attempts, proxy timeouts, and gateway stream errors before attributing a cause."]
    else:
        next_checks = ["Collect measurements and logs specific to the triggering alert; request counters and trace relationships alone do not establish its cause."]
    impact["counter_sample_count"] = sum(r["metric"] == "request_count" for r in metrics)
    impact["measurements"] = [m for m in impact["measurements"] if m["metric"] in ("error_rate_ratio", "latency_p99_ms")]
    dependencies = [r for r in records if r["kind"] == "trace" and r.get("error") and r.get("peer_service")]
    candidates = [{"hypothesis": "Failed call to dependency", "dependency": r["peer_service"],
                   "evidence_ids": [r["evidence_id"]],
                   "missing_evidence": "Dependency-side evidence and causal verification"} for r in dependencies]
    spans = {}
    for r in records:
        if r["kind"] == "trace": spans.setdefault((r["source_id"],r["trace_id"],r["span_id"]),[]).append(r)
    lineage_cache={}
    def valid_lineage(key):
        path=[]; seen=set()
        while key in spans and key not in lineage_cache:
            if key in seen or len(spans[key])!=1:
                for item in path: lineage_cache[item]=False
                return False
            seen.add(key); path.append(key)
            span=spans[key][0]
            key=(span["source_id"],span["trace_id"],span.get("parent_span_id"))
        valid=lineage_cache.get(key,True)
        for item in path: lineage_cache[item]=valid
        return valid
    relationships=[]
    for key,matches in spans.items():
        if not valid_lineage(key): continue
        if len(matches)!=1: continue
        child=matches[0]
        parents=spans.get((child["source_id"],child["trace_id"],child.get("parent_span_id")),[])
        if len(parents)!=1 or parents[0]["span_id"]==child["span_id"]: continue
        parent=parents[0]
        if instant(child["observed_at"]) < instant(parent["observed_at"]): continue
        relationships.append({"relationship":"observed_parent_child","parent_evidence_id":parent["evidence_id"],
            "child_evidence_id":child["evidence_id"],"both_spans_failed":parent["error"] and child["error"],
            "causality_verified":False})
    failed_spans = [r for r in records if r["kind"] == "trace" and r.get("error") and r["service"]==request.get("service",r["service"])]
    service = request.get("service", "the selected service")
    impact["affected_service"] = service
    impact["summary"] = f"Collected telemetry for {service} does not quantify affected users, failed requests, or business loss."
    summary = "No causal explanation is supported by the collected evidence."
    if errors:
        impact["summary"] = f"Nonzero error-rate samples were observed for {service}. They do not establish affected user counts or business loss."
    elif failed_spans:
        impact["status"] = "observed_failed_spans"
        impact["evidence_ids"] = [r["evidence_id"] for r in failed_spans]
        impact["summary"] = f"{len(failed_spans)} collected spans report errors for {service}. Sampled spans do not establish the total number of failed requests or affected users."
    if candidates:
        summary = "Failed dependency calls were observed. Dependency-side evidence is still needed to determine whether they caused the incident."
    if sse:
        if all(r["value"] == 0 for r in sse):
            impact["operational_observation"] = "No SSE subscribers were observed in the collected series during this window. The data does not show whether users expected live updates or used polling."
            summary = "The collected connection samples are all zero. This supports the no-connected-clients condition, but cannot distinguish an idle UI from failed connection attempts."
        else:
            summary = "Connected SSE clients appear in the sampled window; the collected data does not show a continuous absence of clients."
    operations = {}
    for span in failed_spans:
        name=span.get("operation") or "Operation not recorded"
        group=operations.setdefault(name,{"operation":name,"span_count":0,"trace_ids":set(),"evidence_ids":[],"failure_details":set()})
        group["span_count"]+=1
        group["trace_ids"].add((span["source_id"],span["trace_id"]))
        group["evidence_ids"].append(span["evidence_id"])
        if "http_status_code" in span:group["failure_details"].add("HTTP "+str(span["http_status_code"]))
        if "rpc_status_code" in span:group["failure_details"].add("gRPC status "+str(span["rpc_status_code"]))
        group["failure_details"].update(span.get("error_types",[]))
    affected_operations=[]
    for name,group in sorted(operations.items()):
        affected_operations.append({**group,"trace_ids":None,"sampled_traces":len(group["trace_ids"]),
            "failure_details":sorted(group["failure_details"])})
    impact["affected_operations"]=affected_operations
    impact["sampled_error_traces"]=len({(r["source_id"],r["trace_id"]) for r in failed_spans})
    if failed_spans:
        impact["summary"]=f"{len(failed_spans)} errored spans across {impact['sampled_error_traces']} sampled traces affect {len(affected_operations)} recorded operations in {service}. Nested spans can describe the same request; these counts must not be added together as failed requests."
        if not candidates:
            summary="Errors were recorded in the operations below. The available evidence localizes the failures, but does not establish their underlying cause."
        next_checks=["Inspect the recorded failure and server-side logs for "+group["operation"]+" during the incident window." for group in affected_operations[:5]]
    analysis_findings=[{"finding":"Error recorded in "+group["operation"],"details":group["failure_details"] or ["This trace records an error flag without a retained failure reason."],
        "evidence_ids":group["evidence_ids"],"sampled_traces":group["sampled_traces"]} for group in affected_operations]
    from .latency import findings as latency_findings
    latency=latency_findings(records, request.get("service"))
    analysis_findings=analysis_findings+latency
    # Reference excerpts provide context only; they never become incident evidence.
    terms = [service.lower()]
    if sse or "sse" in str(request.get("origin",{}).get("name", "")).lower():
        terms += ["sse", "server-sent", "live updates", "polling"]
    references = []
    for document in documents:
        content = document.get("content", "")
        matches = [line.strip() for line in content.splitlines() if any(term in line.lower() for term in terms if term)]
        if matches:
            references.append({"document_id":document["document_id"],"source_uri":document["source_uri"],
                "excerpt":" ".join(matches[:3])[:1200],"authority":"reference_only"})
        if len(references) == 5: break
    return {"rca": {"status": "hypotheses_only" if candidates else "insufficient_evidence",
                    "confirmed_cause": None, "candidates": candidates, "trace_relationships":relationships,
                    "observations":observations,"next_checks":next_checks,"summary":summary,
                    "reference_context":references,"failure_findings":analysis_findings,"trigger":request.get("origin",{}).get("name"),
                    "context_limit":"Reference documents describe intended or historical behavior; they are not proof of the current cause."},
            "impact": impact, "source_outcomes": evidence["source_outcomes"],
            "resolution": {"status": "blocked", "reason": "No verified cause or approved remediation"},
            "qualification": "deterministic_evidence_assessment", "remote_model_used": False}
