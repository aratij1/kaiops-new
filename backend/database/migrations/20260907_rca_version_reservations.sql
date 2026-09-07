-- Reserve RCA generations before concurrent investigations begin.
CREATE TABLE IF NOT EXISTS incident_rca_version_reservations (
 recommendation_id CHAR(32) NOT NULL PRIMARY KEY,
 tenant_id VARCHAR(128) NOT NULL,
 incident_id CHAR(32) NOT NULL,
 rca_version INT NOT NULL,
 UNIQUE KEY uq_rca_reserved_version (tenant_id, incident_id, rca_version)
) ENGINE=InnoDB;
