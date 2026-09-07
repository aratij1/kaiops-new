"""Safety regressions for archival and restoration; no live database writes."""
import importlib.util
import json
import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
import pytest

spec=importlib.util.spec_from_file_location("retention",Path(__file__).parents[1]/"manage_alert_retention.py")
retention=importlib.util.module_from_spec(spec);spec.loader.exec_module(retention)
POLICY=json.loads((Path(__file__).parents[2]/"backend/config/alert-retention.json").read_text())

def connection():
    db=MagicMock();cursor=db.cursor.return_value.__enter__.return_value
    return db,cursor

def row():
    data={k:None for k in retention.COLUMNS}
    data.update(id="1"*32,tenant_id="default",payload='{ "value": 0.9874999999999999 }',created_at=datetime(2026,1,1),updated_at=datetime(2026,1,1))
    return data

def test_dry_run_never_creates_archives_or_mutates_alerts():
    db,c=connection();c.fetchone.return_value={"eligible":4}
    assert retention.run(db,POLICY)["eligible"]==4
    assert c.execute.call_count==1
    assert c.execute.call_args.args[0].startswith("SELECT COUNT")
    db.begin.assert_not_called();db.commit.assert_not_called()

@pytest.mark.parametrize("key,value",[("unlinked_live_days",29),("archive_minimum_days",364),("automatic_archive_deletion",True),("preserve_incident_and_analysis_references",False),("batch_size",501)])
def test_unsafe_policy_rejected_before_any_sql(key,value):
    db,c=connection()
    with pytest.raises(ValueError):retention.run(db,{**POLICY,key:value},execute=True)
    c.execute.assert_not_called()

def test_archive_failure_rolls_back_source_deletion():
    db,c=connection();c.fetchall.return_value=[row()];c.fetchone.return_value=None;c.rowcount=0
    with pytest.raises(ValueError,match="Source alert changed"):retention.run(db,POLICY,execute=True)
    db.rollback.assert_called_once();assert db.commit.call_count==1  # DDL only; data transaction was not committed.
    statements=[call.args[0] for call in c.execute.call_args_list]
    assert statements.index(next(s for s in statements if s.startswith("INSERT INTO retained"))) < statements.index(next(s for s in statements if s.startswith("DELETE")))

@pytest.mark.parametrize("failure",["checksum","identity","existing"])
def test_restore_rejects_corruption_and_overwrite(failure):
    db,c=connection();data=row();raw=retention.encode_record(data)
    archived={"record_json":raw,"checksum_sha256":hashlib.sha256(raw.encode()).hexdigest(),"alert_id":data["id"]}
    if failure=="checksum":archived["checksum_sha256"]="0"*64
    if failure=="identity":archived["alert_id"]="2"*32
    c.fetchall.return_value=[archived];c.fetchone.return_value={**data,"name":"changed"}
    with pytest.raises(ValueError):retention.run(db,POLICY,execute=True,restore_batch="11111111-1111-4111-8111-111111111111")
    db.rollback.assert_called_once()
    assert not any(call.args[0].startswith("INSERT INTO alerts") for call in c.execute.call_args_list)

def test_restore_preserves_raw_payload_and_archive():
    db,c=connection();data=row();raw=retention.encode_record(data)
    c.fetchall.return_value=[{"record_json":raw,"checksum_sha256":hashlib.sha256(raw.encode()).hexdigest(),"alert_id":data["id"]}]
    c.fetchone.return_value=None
    assert retention.run(db,POLICY,execute=True,restore_batch="11111111-1111-4111-8111-111111111111")["restored"]==1
    insert=next(call for call in c.execute.call_args_list if call.args[0].startswith("INSERT INTO alerts"))
    assert insert.args[1][retention.COLUMNS.index("payload")]==data["payload"]
    assert not any(call.args[0].startswith("DELETE") for call in c.execute.call_args_list)
    db.rollback.assert_not_called()
