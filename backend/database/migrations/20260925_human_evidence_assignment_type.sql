-- Forward-only migration to add assignment_type column to human_evidence_requests for governed HITL routing.
ALTER TABLE human_evidence_requests
    ADD COLUMN assignment_type VARCHAR(32) NOT NULL DEFAULT 'user';
