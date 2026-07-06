CREATE TABLE IF NOT EXISTS refinery.workflow_tasks (
  doc_id STRING NOT NULL,
  status STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  error STRING,
  CONSTRAINT valid_task_status CHECK (
    status IN (
      'landed', 'classified', 'extracted', 'validated',
      'gate_a_pending', 'gate_a_approved', 'gold_landed', 'failed'
    )
  )
) USING DELTA;

CREATE TABLE IF NOT EXISTS refinery.gate_a_decisions (
  doc_id STRING NOT NULL,
  approved BOOLEAN NOT NULL,
  decided_by STRING NOT NULL,
  decided_at TIMESTAMP NOT NULL,
  note STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS refinery.golden_set_results (
  run_id STRING NOT NULL,
  doc_class STRING NOT NULL,
  extractor_version STRING NOT NULL,
  constitution_version STRING NOT NULL,
  document_count INT NOT NULL,
  owner_verified_document_count INT NOT NULL,
  total_fields INT NOT NULL,
  correct_fields INT NOT NULL,
  field_accuracy DOUBLE NOT NULL,
  run_at TIMESTAMP NOT NULL,
  release_blocked BOOLEAN NOT NULL
) USING DELTA;
