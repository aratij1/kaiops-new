-- Migration: 20261012_incident_projections_created_at.sql
-- Description: Adds two missing columns that were defined in ORM models but
--              never added by a migration, causing pipeline-blocking SQL errors:
--              1. incident_projections.created_at  -> broke alert-intelligence / RCA
--              2. approval_assignments.jira_synced -> broke resolution-agent / approvals

-- 1. incident_projections.created_at
SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = DATABASE()
       AND table_name   = 'incident_projections'
       AND column_name  = 'created_at') = 0,
    'ALTER TABLE incident_projections
     ADD COLUMN created_at DATETIME(6) NOT NULL
         DEFAULT CURRENT_TIMESTAMP(6)
         AFTER first_seen_at',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Backfill created_at from first_seen_at for existing rows
UPDATE incident_projections
SET    created_at = first_seen_at
WHERE  created_at != first_seen_at;

-- 2. approval_assignments.jira_synced
SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = DATABASE()
       AND table_name   = 'approval_assignments'
       AND column_name  = 'jira_synced') = 0,
    'ALTER TABLE approval_assignments
     ADD COLUMN jira_synced TINYINT(1) NOT NULL DEFAULT 0
         AFTER assignment_reason',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Index on jira_synced for Jira sync queries
SET @sql := IF(
    (SELECT COUNT(*) FROM information_schema.statistics
     WHERE table_schema = DATABASE()
       AND table_name   = 'approval_assignments'
       AND index_name   = 'idx_approval_assignments_jira_synced') = 0,
    'ALTER TABLE approval_assignments ADD INDEX idx_approval_assignments_jira_synced (jira_synced)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
