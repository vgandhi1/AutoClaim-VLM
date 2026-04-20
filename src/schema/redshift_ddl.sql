-- Reference DDL mirrored in db/migrations for Redshift deployments.

CREATE SCHEMA IF NOT EXISTS vehicle_damage;

CREATE TABLE IF NOT EXISTS vehicle_damage.vehicle_damage_claims (
    claim_id VARCHAR(64) NOT NULL,
    image_s3_key VARCHAR(1024),
    damage_class VARCHAR(128),
    damage_severity VARCHAR(32),
    vlm_confidence DOUBLE PRECISION,
    pipeline_action VARCHAR(64),
    ingested_at TIMESTAMP DEFAULT GETDATE()
);

CREATE TABLE IF NOT EXISTS vehicle_damage.vlm_inference_log (
    inference_id VARCHAR(64) NOT NULL,
    claim_id VARCHAR(64),
    model_id VARCHAR(256),
    latency_ms INTEGER,
    prompt_version VARCHAR(32),
    ingested_at TIMESTAMP DEFAULT GETDATE()
);
