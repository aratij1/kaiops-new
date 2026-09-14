"""Native read-only Prometheus raw-sample and Loki log adapters.

Queries are built from server-owned names/equality selectors, never client expressions.
"""
import hashlib
import json
import math
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote
from .incidents import instant
from .handoff import encode

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def nanoseconds(value):
    delta = instant(value) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000000000 + delta.microseconds * 1000


def selectors(endpoint, request):
    label = endpoint.get("service_label", "service_name")
    labels = dict(endpoint.get("labels", {}))
    if label in labels and labels[label] != request["service"]:
        raise ValueError("Conflicting service selector")
    if endpoint.get("fixed_service"):
        if endpoint["fixed_service"] != request["service"] or not labels:
            raise ValueError("Source is restricted to a different service")
    else:
        labels[label] = request["service"]
    if not labels or any(not isinstance(k, str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", k)
                         or not isinstance(v, str) for k, v in labels.items()):
        raise ValueError("Invalid labels")
    return "{" + ",".join(k + "=" + json.dumps(v, ensure_ascii=True) for k, v in sorted(labels.items())) + "}"


def native_request(endpoint, request, limit):
    kind = endpoint.get("type", "normalized")
    if kind == "normalized": return endpoint["url"], request
    if kind == "jaeger":
        from .jaeger import query
        return query(endpoint, request, limit)
    selector = selectors(endpoint, request)
    base = endpoint["url"].rstrip("/")
    if kind == "prometheus":
        metric = endpoint["metric_name"]
        if not isinstance(metric, str) or not re.fullmatch(r"[a-zA-Z_:][a-zA-Z0-9_:]*", metric):
            raise ValueError("Require a raw metric name, not a PromQL expression")
        if endpoint["metric"] not in ("error_rate_ratio", "latency_p99_ms", "request_count", "sse_connections"):
            raise ValueError("Unsupported metric meaning")
        multiplier = endpoint.get("multiplier", 1)
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or not math.isfinite(multiplier) or multiplier <= 0:
            raise ValueError("Invalid metric unit conversion")
        seconds = math.ceil((instant(request["window_end"]) - instant(request["window_start"])).total_seconds()) + 1
        # Instant range-vector queries return raw samples. Extra second includes the
        # left boundary; incident filtering removes any earlier samples afterward.
        return base + "/api/v1/query", {"query": metric + selector + "[" + str(seconds) + "s]",
                                      "time": request["window_end"]}
    if kind == "loki":
        return base + "/loki/api/v1/query_range", {"query": selector, "start": str(nanoseconds(request["window_start"])),
            "end": str(nanoseconds(request["window_end"]) + 1), "direction": "forward", "limit": limit}
    raise ValueError("Unknown telemetry adapter")


def decode_native(payload, endpoint, source, request, limit):
    kind = endpoint.get("type", "normalized")
    if kind == "normalized": return payload["records"], 0, []
    if kind == "jaeger":
        from .jaeger import decode
        return decode(payload, endpoint, source, request, limit)
    if payload["status"] != "success": raise ValueError("Source query failed")
    data = payload["data"]
    expected = "matrix" if kind == "prometheus" else "streams"
    if data["resultType"] != expected or not isinstance(data["result"], list):
        raise ValueError("Unexpected native result type")
    records, rejected, warnings = [], 0, []
    if payload.get("warnings"): warnings.append("source_query_warnings")
    label = endpoint.get("service_label", "service_name")
    count = 0
    for series in data["result"]:
        labels = series["metric" if kind == "prometheus" else "stream"]
        if not isinstance(labels, dict) or not isinstance(series["values"], list):
            raise ValueError("Invalid series")
        identity = hashlib.sha256(encode(labels).encode()).hexdigest()
        for sample in series["values"]:
            count += 1
            if count > limit: raise ValueError("Native sample limit exceeded")
            try:
                if endpoint.get("fixed_service",labels.get(label)) != request["service"] or any(labels.get(k) != v for k, v in endpoint.get("labels", {}).items()):
                    raise ValueError("Unrelated series")
                stamp, value = sample[:2]
                if kind == "prometheus":
                    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
                        raise ValueError("Invalid timestamp")
                    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                        raise ValueError("Invalid metric value")
                    observed = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
                    records.append({"kind": "metric", "service": endpoint.get("fixed_service",labels.get(label)), "observed_at": observed,
                        "series_labels": labels, "metric": endpoint["metric"], "value": float(value) * endpoint.get("multiplier", 1),
                        "source_uri": "metric://" + source + "/" + identity})
                else:
                    if not isinstance(stamp, str) or not stamp.isdigit(): raise ValueError("Invalid Loki timestamp")
                    ns = int(stamp)
                    if not nanoseconds(request["window_start"]) <= ns <= nanoseconds(request["window_end"]):
                        raise ValueError("Outside incident window")
                    for path_key in ("filename", "path", "file_path"):
                        path = unquote(str(labels.get(path_key, ""))).replace("\\", "/").lower()
                        if any(part in path for part in ("landing/", "ingested_alerts/")):
                            raise ValueError("Alert ingestion artifact")
                    observed = (EPOCH + timedelta(microseconds=ns // 1000)).isoformat()
                    records.append({"kind": "log", "service": endpoint.get("fixed_service",labels.get(label)), "observed_at": observed,
                        "series_labels": labels, "message": value, "source_uri": "log://" + source + "/" + identity + "/" + stamp})
            except (ValueError, TypeError, KeyError, OverflowError, OSError): rejected += 1
    if kind == "loki" and count == limit: warnings.append("log_limit_reached")
    return records, rejected, warnings
