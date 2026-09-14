"""Automatic scoped firing-alert admission into the durable incident pipeline."""
import hashlib
from datetime import datetime,timezone,timedelta
from sqlalchemy.exc import NoResultFound
from .incidents import instant
from .handoff import encode
from .live_alerts import live_alerts

class AlertIntake:
    def __init__(self,store,endpoints,collect=live_alerts):
        self.store,self.endpoints,self.collect=store,endpoints,collect

    async def scan(self,tenant,application):
        app=self.store.store.application(tenant,application)
        snapshot=await self.collect(app["config"],self.endpoints)
        report={"checked_at":snapshot["checked_at"],"source_status":snapshot["status"],
            "source_outcomes":snapshot["source_outcomes"],"created":0,"existing":0,"skipped":0,"incident_ids":[]}
        for alert in snapshot["alerts"]:
            if alert["state"]!="firing":report["skipped"]+=1;continue
            try:
                started=instant(alert["active_at"])
                now=datetime.now(timezone.utc)
                if started>now+timedelta(minutes=1):raise ValueError("Future activation")
                fingerprint=alert["fingerprint"]
                if not isinstance(fingerprint,str) or len(fingerprint)!=64:raise ValueError("Invalid fingerprint")
            except (KeyError,TypeError,ValueError,AttributeError):report["skipped"]+=1;continue
            # Stable occurrence identity excludes polling time, mutable annotations,
            # and source aliases; labels and activation distinguish new occurrences.
            incident="alert-"+hashlib.sha256(encode([fingerprint,started.isoformat()]).encode()).hexdigest()[:32]
            try:
                self.store.get(tenant,application,incident)
                report["existing"]+=1;continue
            except NoResultFound:pass
            request={"service":alert["service"],"window_start":(now-timedelta(minutes=2)).isoformat(),"window_end":now.isoformat(),
                "origin":{"kind":"prometheus_alert","name":alert["name"],"source_id":alert["source_id"],
                    "active_at":started.isoformat(),"fingerprint":fingerprint,"severity":alert["severity"],
                    "window_policy":"two_minutes_before_first_detection"}}
            try:
                created=self.store.admit(tenant,application,incident,request)
            except ValueError:
                # A concurrent poll may already have committed a different detection
                # window. Only tolerate that race if the exact occurrence exists.
                row=self.store.get(tenant,application,incident)
                if row["request"].get("origin",{}).get("fingerprint")!=fingerprint:raise
                created=False
            report["created" if created else "existing"]+=1
            if created:report["incident_ids"].append(incident)
        return report
