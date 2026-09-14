"""Durable operator feedback for the agent learning loop."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, Text, Table, insert, select
from .handoff import metadata, write_transaction

feedback = Table("next_incident_feedback", metadata,
    Column("feedback_id", String(36), primary_key=True),
    Column("tenant_id", String(128), nullable=False), Column("application_id", String(128), nullable=False),
    Column("incident_id", String(128), nullable=False), Column("decision", String(32), nullable=False),
    Column("reason_category", String(64)), Column("corrected_cause", Text), Column("missing_evidence", Text),
    Column("comment", Text), Column("created_at", String(64), nullable=False))

def submit(engine, tenant, application, incident, payload):
    decision=payload.get("decision")
    if decision not in {"helpful","incorrect","incomplete"}: raise ValueError("Decision must be helpful, incorrect or incomplete")
    if decision != "helpful" and not payload.get("reason_category"): raise ValueError("A reason category is required for corrective feedback")
    values={"feedback_id":str(uuid4()),"tenant_id":tenant,"application_id":application,"incident_id":incident,"decision":decision,
      "reason_category":str(payload.get("reason_category") or "")[:64],"corrected_cause":str(payload.get("corrected_cause") or "")[:4000],
      "missing_evidence":str(payload.get("missing_evidence") or "")[:4000],"comment":str(payload.get("comment") or "")[:4000],
      "created_at":datetime.now(timezone.utc).isoformat()}
    with write_transaction(engine) as c:c.execute(insert(feedback).values(**values))
    return values

def list_feedback(engine, tenant, application, incident):
    with engine.connect() as c:return [dict(x) for x in c.execute(select(feedback).where(feedback.c.tenant_id==tenant,feedback.c.application_id==application,feedback.c.incident_id==incident).order_by(feedback.c.created_at.desc())).mappings()]
