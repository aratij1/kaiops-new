"""Bounded adapter for the version-sensitive Jaeger Query HTTP JSON API."""
import json
import re
from datetime import timedelta
from .native_telemetry import EPOCH, nanoseconds


def query(endpoint, request, limit):
    tags=endpoint.get("tags", {})
    if not isinstance(tags, dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in tags.items()):
        raise ValueError("Invalid Jaeger scope tags")
    return endpoint["url"].rstrip("/")+"/api/traces", {
        "service":request["service"], "start":nanoseconds(request["window_start"])//1000,
        "end":nanoseconds(request["window_end"])//1000, "limit":min(limit,20),
        "tags":json.dumps(tags,sort_keys=True)}


def identity(value, lengths):
    if not isinstance(value,str) or len(value) not in lengths or not re.fullmatch(r"[0-9a-fA-F]+",value) or int(value,16)==0:
        raise ValueError("Invalid trace identity")
    return value.lower().zfill(max(lengths))


def tag_values(tags):
    if not isinstance(tags,list): raise ValueError("Invalid span tags")
    values={}
    for tag in tags:
        key=tag["key"]
        if key in values: raise ValueError("Ambiguous duplicate tag")
        values[key]=tag["value"]
    return values


def decode(payload, endpoint, source, request, limit):
    traces=payload["data"]
    if not isinstance(traces,list): raise ValueError("Invalid Jaeger response")
    records,rejected,warnings=[],0,[]
    if payload.get("errors"): warnings.append("trace_query_errors")
    if len(traces)>=min(limit,20): warnings.append("trace_limit_reached")
    start,end=nanoseconds(request["window_start"])//1000,nanoseconds(request["window_end"])//1000
    count=0
    for trace in traces:
        trace_id=identity(trace["traceID"],(16,32))
        processes=trace["processes"]
        if not isinstance(processes,dict) or not isinstance(trace["spans"],list): raise ValueError("Invalid trace shape")
        if trace.get("warnings"): warnings.append("trace_warnings")
        allowed=set(endpoint.get("dependency_services",{}).get(request["service"],[]))
        reachable={s.get("spanID") for s in trace["spans"] if processes.get(s.get("processID"),{}).get("serviceName")==request["service"]}
        for _ in range(min(len(trace["spans"]),100)):
            added={s.get("spanID") for s in trace["spans"] if processes.get(s.get("processID"),{}).get("serviceName") in allowed and any(r.get("refType")=="CHILD_OF" and r.get("traceID")==trace["traceID"] and r.get("spanID") in reachable for r in s.get("references",[]))}
            if added<=reachable:break
            reachable.update(added)
        for span in trace["spans"]:
            count+=1
            if count>limit: raise ValueError("Trace span limit exceeded")
            try:
                if identity(span["traceID"],(16,32))!=trace_id: raise ValueError("Cross-trace span")
                process=processes[span["processID"]]
                if process["serviceName"]!=request["service"] and (process["serviceName"] not in allowed or span.get("spanID") not in reachable):
                    # Only explicitly configured descendants belong to this investigation.
                    continue
                tags=tag_values(span.get("tags",[]));resource=tag_values(process.get("tags",[]))
                scope=endpoint.get("tags",{})
                for key,value in scope.items():
                    if (key in tags and tags[key]!=value) or (key in resource and resource[key]!=value) or (key not in tags and key not in resource):
                        raise ValueError("Span scope mismatch")
                stamp,duration=span["startTime"],span["duration"]
                if any(isinstance(v,bool) or not isinstance(v,int) for v in (stamp,duration)) or duration<0 or not start<=stamp<=end:
                    raise ValueError("Invalid span time")
                span_id=identity(span["spanID"],(16,))
                parents=[]
                for ref in span.get("references",[]):
                    if ref["refType"]=="CHILD_OF":
                        if identity(ref["traceID"],(16,32))!=trace_id: raise ValueError("Cross-trace parent")
                        parents.append(identity(ref["spanID"],(16,)))
                if len(set(parents))>1 or span_id in parents: raise ValueError("Ambiguous or self parent")
                peer=tags.get("peer.service")
                if peer is not None and (not isinstance(peer,str) or not peer or len(peer)>128): raise ValueError("Invalid dependency")
                error=tags.get("error") is True or tags.get("otel.status_code")=="ERROR"
                record={"kind":"trace","service":process["serviceName"],"observed_at":(EPOCH+timedelta(microseconds=stamp)).isoformat(),
                    "source_uri":"trace://"+source+"/"+trace_id+"/"+span_id,"trace_id":trace_id,"span_id":span_id,
                    "parent_span_id":parents[0] if parents else None,"peer_service":peer,"error":error,
                    "duration_ms":duration/1000,"operation":span["operationName"]}
                http_status=tags.get("http.response.status_code",tags.get("http.status_code"))
                if isinstance(http_status,int) and not isinstance(http_status,bool) and 100<=http_status<=599:
                    record["http_status_code"]=http_status
                rpc_status=tags.get("rpc.grpc.status_code")
                if isinstance(rpc_status,int) and not isinstance(rpc_status,bool) and 0<=rpc_status<=16:
                    record["rpc_status_code"]=rpc_status
                exception_types=[]
                for log in span.get("logs",[])[:20]:
                    for field in log.get("fields",[])[:30]:
                        if field.get("key")=="exception.type" and isinstance(field.get("value"),str):
                            exception_types.append(field["value"][:256])
                failure_type=tags.get("error.type",tags.get("exception.type"))
                if isinstance(failure_type,str):exception_types.append(failure_type[:256])
                if exception_types: record["error_types"]=sorted(set(exception_types))[:5]
                records.append(record)
                if span.get("warnings") or process.get("warnings"): warnings.append("trace_warnings")
            except (ValueError,KeyError,TypeError,OverflowError): rejected+=1
    return records,rejected,sorted(set(warnings))
