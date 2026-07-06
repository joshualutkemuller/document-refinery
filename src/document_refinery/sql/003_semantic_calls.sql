CREATE TABLE IF NOT EXISTS refinery.semantic_model_calls (
  doc_id STRING NOT NULL,
  role STRING NOT NULL,
  provider STRING NOT NULL,
  model STRING NOT NULL,
  session_id STRING NOT NULL,
  response_id STRING NOT NULL,
  prompt_version STRING NOT NULL,
  schema_version STRING NOT NULL,
  constitution_version STRING NOT NULL,
  language STRING NOT NULL,
  request_hash STRING NOT NULL,
  response_hash STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  CONSTRAINT valid_semantic_role CHECK (role IN ('extractor', 'validator'))
) USING DELTA;

