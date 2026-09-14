"""Application overview reads; never infer live health from registration or discovery."""
from sqlalchemy import select,func
from .incidents import incidents,baselines


def overview(store,tenant,application,endpoints):
    app=store.application(tenant,application)
    with store.engine.connect() as c:
        counts=dict(c.execute(select(incidents.c.state,func.count()).where(incidents.c.tenant_id==tenant,
            incidents.c.application_id==application).group_by(incidents.c.state)).all())
        ref=c.execute(select(baselines.c.artifact_ref).where(baselines.c.tenant_id==tenant,
            baselines.c.application_id==application)).scalar_one_or_none()
    baseline=store.artifact(tenant,application,ref) if ref else {}
    manifest_ref=baseline.get("manifest_ref")
    manifest=store.artifact(tenant,application,manifest_ref) if manifest_ref else {}
    documents=[{k:doc.get(k) for k in ("document_id","source_id","source_uri","collected_at")} for doc in manifest.get("documents",[])]
    return {"application_id":application,"discovery_state":app["state"],"baseline_ready":baseline.get("baseline_ready",False),
        "health":{"status":"unknown","reason":"No qualified service health policy configured"},
        "services":[{"name":name,"health":"unknown"} for name in app["config"].get("services",[])],
        "incidents":{"total":sum(counts.values()),"by_state":counts,
            "in_progress":sum(counts.get(s,0) for s in ("waiting_for_context","collection_queued","analysis_queued","resolution_queued","execution_queued","verification_queued")),
            "blocked_or_failed":sum(counts.get(s,0) for s in ("context_blocked","failed","resolution_failed")),"assessed":counts.get("assessed",0)},
        "sources":[{"id":key,"type":endpoints.get(key,{}).get("type","normalized"),
            "configuration":"configured" if key in endpoints else "not_configured","connectivity":"not_checked"}
            for key in app["config"].get("telemetry_sources",[])],
        "documents":documents,"document_outcomes":baseline.get("source_outcomes",manifest.get("sources",[])),
        "manifest_ref":manifest_ref,"baseline_ref":ref}
