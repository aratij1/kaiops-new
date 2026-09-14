"""Read-only scoped Prometheus alert snapshots; no incident creation or health inference."""
import asyncio,json,hashlib
from datetime import datetime,timezone
import httpx

async def live_alerts(config,endpoints,transport=None):
    semaphore=asyncio.Semaphore(4)
    async def one(key,endpoint):
        outcome={"source_id":key,"status":"failed"}
        async with semaphore:
            try:
                async with asyncio.timeout(2):
                    async with httpx.AsyncClient(timeout=2,transport=transport,trust_env=False,follow_redirects=False) as client:
                        async with client.stream("GET",endpoint["url"].rstrip("/")+"/api/v1/alerts",headers=endpoint.get("headers",{})) as response:
                            response.raise_for_status();body=bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body)>2097152: raise ValueError("Response limit")
                payload=json.loads(body)
                if payload.get("status")!="success": raise ValueError("Query failed")
                rows=payload["data"]["alerts"]
                if not isinstance(rows,list) or len(rows)>5000: raise ValueError("Alert limit")
                matches=[];excluded=0
                for row in rows:
                    labels=row.get("labels",{});service=labels.get(endpoint.get("service_label","service_name"))
                    if service not in config.get("services",[]) or any(labels.get(k)!=v for k,v in endpoint.get("alert_labels",endpoint.get("labels",{})).items()):
                        excluded+=1;continue
                    if row.get("state") not in ("pending","firing"):continue
                    matches.append({"source_id":key,"name":str(labels.get("alertname","Unnamed alert"))[:256],"service":service,
                        "fingerprint":hashlib.sha256(json.dumps(labels,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                        "state":row["state"],"severity":str(labels.get("severity","not recorded"))[:128],
                        "summary":str(row.get("annotations",{}).get("summary",""))[:2048],"active_at":row.get("activeAt")})
                outcome.update(status="partial" if len(matches)>100 or payload.get("warnings") else "collected",excluded_outside_scope=excluded)
                return outcome,matches[:100]
            except (TimeoutError,httpx.TimeoutException): outcome["status"]="timed_out"
            except (httpx.HTTPError,ValueError,KeyError,TypeError,AttributeError): pass
            return outcome,[]
    selected=[(key,endpoints[key]) for key in config.get("telemetry_sources",[]) if endpoints.get(key,{}).get("type")=="prometheus" and endpoints[key].get("collect_alerts",True)]
    results=await asyncio.gather(*(one(key,endpoint) for key,endpoint in selected))
    return {"checked_at":datetime.now(timezone.utc).isoformat(),"status":"not_configured" if not selected else (
        "collected" if all(outcome["status"]=="collected" for outcome,_ in results) else "partial_or_unavailable"),
        "source_outcomes":[outcome for outcome,_ in results],"alerts":[row for _,rows in results for row in rows],
        "scope_note":"Only alerts matching registered services and all configured scope labels are shown. An empty result does not establish service health."}
