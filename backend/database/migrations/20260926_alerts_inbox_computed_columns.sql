-- Migration: 20260926_alerts_inbox_computed_columns.sql
-- Description: Adds virtual generated columns inbox_project and inbox_canonical_incident_id
--              and composite indexes to kaiops.alerts table to support fast inbox projection queries.

-- 1. Add inbox_project virtual generated column
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'alerts' AND column_name = 'inbox_project') = 0,
    'ALTER TABLE alerts ADD COLUMN inbox_project VARCHAR(255) GENERATED ALWAYS AS (LOWER(COALESCE(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.project_id\')), \'null\'), NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.project\')), \'null\'), NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.project_name\')), \'null\'), NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.application\')), \'null\'), NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.labels.project_id\')), \'null\'), NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.labels.project\')), \'null\'), NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.labels.project_name\')), \'null\'), NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.labels.application\')), \'null\'), \'\'))) VIRTUAL',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. Add inbox_canonical_incident_id virtual generated column
SET @sql := IF((SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'alerts' AND column_name = 'inbox_canonical_incident_id') = 0,
    'ALTER TABLE alerts ADD COLUMN inbox_canonical_incident_id VARCHAR(64) GENERATED ALWAYS AS (NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload, \'$.metadata.deduplication.canonical_incident_id\')), \'null\')) VIRTUAL',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Add idx_alerts_inbox_scope index
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'alerts' AND index_name = 'idx_alerts_inbox_scope') = 0,
    'ALTER TABLE alerts ADD INDEX idx_alerts_inbox_scope (tenant_id, inbox_canonical_incident_id, inbox_project, created_at)',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. Add idx_alerts_inbox_cover index
SET @sql := IF((SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'alerts' AND index_name = 'idx_alerts_inbox_cover') = 0,
    'ALTER TABLE alerts ADD INDEX idx_alerts_inbox_cover (tenant_id, inbox_canonical_incident_id, inbox_project, service, severity, created_at)',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
