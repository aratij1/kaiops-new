"""Durable incident role assignments and append-only governance audit."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, Text, Table, insert, select
from .handoff import metadata, write_transaction, encode

assignments=Table("next_incident_assignments",metadata,
 Column("assignment_id",String(36),primary_key=True),Column("tenant_id",String(128),nullable=False),Column("application_id",String(128),nullable=False),Column("incident_id",String(128),nullable=False),Column("role",String(32),nullable=False),Column("subject",String(256),nullable=False),Column("assigned_by",String(256),nullable=False),Column("assigned_at",String(64),nullable=False))
audit_events=Table("next_governance_audit",metadata,
 Column("audit_id",String(36),primary_key=True),Column("tenant_id",String(128),nullable=False),Column("application_id",String(128),nullable=False),Column("incident_id",String(128),nullable=False),Column("actor",String(256),nullable=False),Column("action",String(64),nullable=False),Column("details",Text,nullable=False),Column("created_at",String(64),nullable=False))
ROLES={"incident_commander","communications_lead","operations_lead"}
def assign(engine,tenant,application,incident,role,subject,actor):
 if role not in ROLES: raise ValueError("Unsupported incident role")
 if not subject.strip(): raise ValueError("Assignment subject is required")
 now=datetime.now(timezone.utc).isoformat();values={"assignment_id":str(uuid4()),"tenant_id":tenant,"application_id":application,"incident_id":incident,"role":role,"subject":subject.strip()[:256],"assigned_by":actor[:256],"assigned_at":now}
 with write_transaction(engine) as c:
  c.execute(insert(assignments).values(**values));c.execute(insert(audit_events).values(audit_id=str(uuid4()),tenant_id=tenant,application_id=application,incident_id=incident,actor=actor[:256],action="role_assigned",details=encode({"role":role,"subject":subject.strip()[:256]}),created_at=now))
 return values
def snapshot(engine,tenant,application,incident):
 with engine.connect() as c:
  a=[dict(x) for x in c.execute(select(assignments).where(assignments.c.tenant_id==tenant,assignments.c.application_id==application,assignments.c.incident_id==incident).order_by(assignments.c.assigned_at.desc())).mappings()]
  h=[dict(x) for x in c.execute(select(audit_events).where(audit_events.c.tenant_id==tenant,audit_events.c.application_id==application,audit_events.c.incident_id==incident).order_by(audit_events.c.created_at.desc()).limit(100)).mappings()]
 return {"assignments":a,"audit":[{**x,"details":__import__('json').loads(x["details"])} for x in h]}
