from pathlib import Path


def test_alerts_inbox_computed_columns_migration_exists_and_valid() -> None:
    migration_path = Path("backend/database/migrations/20260926_alerts_inbox_computed_columns.sql")
    assert migration_path.is_file(), "Migration file 20260926_alerts_inbox_computed_columns.sql must exist"
    
    content = migration_path.read_text(encoding="utf-8")
    assert "inbox_project" in content
    assert "inbox_canonical_incident_id" in content
    assert "idx_alerts_inbox_scope" in content
    assert "idx_alerts_inbox_cover" in content
    assert "GENERATED ALWAYS AS" in content
    assert "VIRTUAL" in content
