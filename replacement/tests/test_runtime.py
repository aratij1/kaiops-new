import sys
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).parents[1]))
from kaims_next import runtime


def test_api_keeps_onboarding_durable_when_broker_is_down(tmp_path,monkeypatch):
    roots=tmp_path/"roots.json";roots.write_text('{}')
    monkeypatch.setenv("NEXT_API_TOKEN","test-token-"+"x"*32)
    monkeypatch.setenv("NEXT_TENANT_ID","tenant-test")
    monkeypatch.setenv("NEXT_DATABASE_URL","sqlite:///"+str(tmp_path/"state.db"))
    monkeypatch.setenv("NEXT_DOCUMENT_ROOTS_FILE",str(roots))
    monkeypatch.setenv("NEXT_RABBITMQ_URL","amqp://unused")
    monkeypatch.setattr(runtime.aio_pika,"connect_robust",AsyncMock(side_effect=ConnectionError()))
    headers={"Authorization":"Bearer test-token-"+"x"*32}
    with TestClient(runtime.create_app()) as client:
        assert client.post("/applications",json={"application_id":"a"}).status_code==401
        response=client.post("/applications",json={"application_id":"a","services":["gateway"],"document_sources":[{"id":"docs","root":"unconfigured"}]},headers=headers)
        assert response.status_code==202
        assert response.json()["state"]=="discovery_queued"
        assert client.get("/healthz").json()["broker_ready"] is False
    with TestClient(runtime.create_app()) as client:
        assert client.get("/applications/a",headers=headers).json()["state"]=="discovery_queued"
        invalid=client.post("/applications",json={"application_id":"b","document_sources":[{"id":"bad","root":[]}]},headers=headers)
        assert invalid.status_code==422

        incident={"incident_id":"i","service":"gateway","window_start":"2026-09-01T10:00:00Z","window_end":"2026-09-01T10:10:00Z"}
        assert client.post("/applications/a/incidents",json=incident).status_code==401
        response=client.post("/applications/a/incidents",json=incident,headers=headers)
        assert response.status_code==202
        assert response.json()["state"]=="waiting_for_context"
        assert client.get("/applications/a/incidents/i",headers=headers).status_code==200
        assert client.get("/applications/a/incidents/i/feedback",headers=headers).json()["items"]==[]
        assert client.post("/applications/a/incidents/i/feedback",json={"decision":"incorrect"},headers=headers).status_code==422
        feedback=client.post("/applications/a/incidents/i/feedback",json={"decision":"incomplete","reason_category":"missing_evidence","missing_evidence":"server logs","comment":"Collect dependency logs next time"},headers=headers)
        assert feedback.status_code==201
        assert client.get("/applications/a/incidents/i/feedback",headers=headers).json()["items"][0]["decision"]=="incomplete"
        assert client.get("/applications/a/incidents/i/governance",headers=headers).json()["assignments"]==[]
        assigned=client.post("/applications/a/incidents/i/assignments",json={"role":"incident_commander","subject":"team-sre"},headers=headers)
        assert assigned.status_code==201
        governance=client.get("/applications/a/incidents/i/governance",headers=headers).json()
        assert governance["multi_user"] is False and governance["assignments"][0]["subject"]=="team-sre"
        assert governance["audit"][0]["action"]=="role_assigned"
        assert client.get("/applications/foreign/incidents/i",headers=headers).status_code==404
        assert client.get("/applications/foreign/artifacts/missing",headers=headers).status_code==404
        incident["service"]="foreign"
        assert client.post("/applications/a/incidents",json=incident,headers=headers).status_code==409

        assert client.get("/").status_code==200
        assert "default-src" in client.get("/").headers["content-security-policy"]
        assert client.get("/source-catalog").status_code==401
        assert client.get("/applications").status_code==401
        assert client.get("/applications/a/incidents").status_code==401
        catalog=client.get("/source-catalog",headers=headers).json()
        assert catalog=={"document_roots":[],"telemetry_sources":[]}
        rows=client.get("/applications?limit=1",headers=headers).json()
        assert rows["items"][0]["application_id"]=="a"
        assert "config" not in rows["items"][0]
        assert client.get("/applications?limit=1000",headers=headers).status_code==422
        rows=client.get("/applications/a/incidents",headers=headers).json()
        assert rows["items"][0]["incident_id"]=="i"
        assert "result" not in rows["items"][0]
        assert client.get("/applications/foreign/incidents",headers=headers).status_code==404

        assert client.post("/applications",json={"application_id":"b"},headers=headers).status_code==202
        first=client.get("/applications?limit=1",headers=headers).json()
        assert first["next"]=="a"
        second=client.get("/applications?limit=1&after=a",headers=headers).json()
        assert [row["application_id"] for row in second["items"]]==["b"]
        assert second["next"] is None

        assert client.get("/applications/a/overview").status_code==401
        overview=client.get("/applications/a/overview",headers=headers).json()
        assert overview["incidents"]["total"]==1
        assert overview["health"]["status"]=="unknown"
        assert client.get("/applications/foreign/overview",headers=headers).status_code==404
        assert client.get("/applications/a/live-alerts").status_code==401
        assert client.get("/applications/a/live-alerts",headers=headers).json()["status"]=="not_configured"

        assert client.get("/workspace").status_code==401
        assert client.get("/incidents").status_code==401
        workspace=client.get("/workspace",headers=headers).json()
        assert workspace["applications"]==2 and workspace["incidents"]==1
        assert workspace["capabilities"]["automatic_remediation"] is False
        assert client.get("/incidents?q=i&state=waiting_for_context",headers=headers).json()["items"][0]["incident_id"]=="i"
        assert client.get("/incidents?q=%25",headers=headers).json()["items"]==[]
        assert client.get("/incidents?offset=-1",headers=headers).status_code==422

        assert client.get("/alerts").status_code==401
        assert client.get("/alerts",headers=headers).json()["items"]==[]
        assert client.get("/incident-intake").status_code==401
        assert client.get("/incident-intake",headers=headers).json()["enabled"] is False
