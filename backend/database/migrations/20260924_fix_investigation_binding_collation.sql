-- Fixes a live production bug: incident_investigation_bindings (created in
-- 20260907_incident_investigation_bindings.sql) was given an explicit
-- utf8mb4_unicode_ci collation, while incidents and incident_projections use
-- MySQL 8's default utf8mb4_0900_ai_ci. That mismatch was harmless while
-- nothing joined across them in raw SQL, but the context reconciliation loop
-- added in 20260921_context_reconciliation_scheduler.sql joins
-- incident_investigation_bindings to both tables on incident_id/alert_id/
-- recommendation_id, and MySQL rejects a direct '=' comparison between
-- differently-collated columns ("Illegal mix of collations"). That crash was
-- repeating on every reconciliation cycle, which is why context enrichment
-- gaps stopped being detected and incidents stayed stuck in investigation.
--
-- Converting the table normalizes every character column to match the rest
-- of the schema and preserves all existing rows; it is not destructive.
ALTER TABLE incident_investigation_bindings
    CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
