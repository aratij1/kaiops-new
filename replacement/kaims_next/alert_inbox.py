"""Scoped live alert inbox with durable investigation links."""
import asyncio, hashlib, json
from datetime import datetime, timezone
from sqlalchemy import select
from .handoff import applications, encode
from .incidents import incidents, instant
from .live_alerts import live_alerts

async def snapshot(store, tenant, endpoints, after="", application_id="", collect=live_alerts):
    conditions=[applications.c.tenant_id==tenant, applications.c.application_id>after]
    if application_id: conditions.append(applications.c.application_id==application_id)
    with store.engine.connect() as c:
        apps=c.execute(select(applications.c.application_id,applications.c.config).where(*conditions)
            .order_by(applications.c.application_id).limit(5)).mappings().all()
    async def one(app):
        data=await collect(json.loads(app["config"]),endpoints)
        rows=[]
        for alert in data["alerts"]:
            incident_id=None
            try:
                incident_id="alert-"+hashlib.sha256(encode([alert["fingerprint"],instant(alert["active_at"]).isoformat()]).encode()).hexdigest()[:32]
            except (KeyError,ValueError,TypeError,AttributeError): pass
            rows.append({**alert,"application_id":app["application_id"],"incident_id":incident_id})
        ids=[r["incident_id"] for r in rows if r["incident_id"]]
        with store.engine.connect() as c:
            linked=dict(c.execute(select(incidents.c.incident_id,incidents.c.state).where(
                incidents.c.tenant_id==tenant,incidents.c.application_id==app["application_id"],incidents.c.incident_id.in_(ids))).all()) if ids else {}
        for row in rows:
            row["incident_state"]=linked.get(row["incident_id"])
            if row["incident_state"] is None: row["incident_id"]=None
        return {"application_id":app["application_id"],"status":data["status"],"source_outcomes":data["source_outcomes"],"alerts":rows}
    results=await asyncio.gather(*(one(app) for app in apps[:4]))
    rows=[row for result in results for row in result["alerts"]]
    rows.sort(key=lambda r:(r["state"]=="firing",r["severity"].lower()=="critical",r.get("active_at") or ""),reverse=True)
    return {"checked_at":datetime.now(timezone.utc).isoformat(),"items":rows,
        "applications":[{k:v for k,v in r.items() if k!="alerts"} for r in results],
        "next":apps[3]["application_id"] if len(apps)>4 else None}
