CREATE SCHEMA IF NOT EXISTS refinery;

CREATE TABLE IF NOT EXISTS refinery.bronze_documents (
  doc_id STRING NOT NULL,
  source STRING NOT NULL,
  counterparty STRING,
  doc_class_hint STRING,
  file_uri STRING NOT NULL,
  file_hash STRING NOT NULL,
  page_count INT,
  received_at TIMESTAMP NOT NULL,
  text_artifact_uri STRING,
  layout_artifact_uri STRING
) USING DELTA
TBLPROPERTIES ('delta.appendOnly' = 'true');

CREATE TABLE IF NOT EXISTS refinery.silver_extractions (
  extraction_id STRING NOT NULL,
  doc_id STRING NOT NULL,
  doc_class STRING NOT NULL,
  extractor_version STRING NOT NULL,
  constitution_version STRING NOT NULL,
  field_path STRING NOT NULL,
  raw_value STRING,
  normalized_value STRING NOT NULL,
  value_type STRING NOT NULL,
  unit STRING,
  currency STRING,
  source_clause STRING NOT NULL,
  source_locator STRING NOT NULL,
  confidence DOUBLE NOT NULL,
  ambiguity_flag BOOLEAN NOT NULL,
  ambiguity_note STRING,
  validator_status STRING NOT NULL,
  corrected_value STRING,
  corrected_by STRING,
  created_at TIMESTAMP NOT NULL,
  CONSTRAINT valid_confidence CHECK (confidence BETWEEN 0.0 AND 1.0),
  CONSTRAINT valid_validator_status
    CHECK (validator_status IN ('pending', 'confirmed', 'disputed', 'corrected'))
) USING DELTA;

CREATE TABLE IF NOT EXISTS refinery.gold_eligibility_terms (
  counterparty STRING NOT NULL,
  agreement_id STRING NOT NULL,
  schedule_version STRING NOT NULL,
  margin_type STRING NOT NULL,
  asset_criterion STRING NOT NULL,
  eligible BOOLEAN NOT NULL,
  haircut_pct DOUBLE,
  concentration_limit_pct DOUBLE,
  concentration_basis STRING,
  currency_scope ARRAY<STRING>,
  rating_floor STRING,
  tenor_cap_days INT,
  valid_from DATE NOT NULL,
  valid_to DATE,
  knowledge_from TIMESTAMP NOT NULL,
  knowledge_to TIMESTAMP,
  silver_extraction_ids ARRAY<STRING> NOT NULL,
  doc_id STRING NOT NULL,
  CONSTRAINT valid_haircut CHECK (haircut_pct IS NULL OR haircut_pct BETWEEN 0.0 AND 100.0),
  CONSTRAINT valid_concentration CHECK (
    concentration_limit_pct IS NULL OR concentration_limit_pct BETWEEN 0.0 AND 100.0
  ),
  CONSTRAINT valid_valid_time CHECK (valid_to IS NULL OR valid_from <= valid_to),
  CONSTRAINT valid_knowledge_time CHECK (
    knowledge_to IS NULL OR knowledge_from <= knowledge_to
  )
) USING DELTA;

