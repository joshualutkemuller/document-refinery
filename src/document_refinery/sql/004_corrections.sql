-- Append-only audit of owner corrections and disputes on silver extractions.
-- Every reviewer action is durable so it can be replayed into constitution
-- rules or golden cases by the distiller learning loop.
CREATE TABLE IF NOT EXISTS refinery.correction_actions (
  doc_id STRING NOT NULL,
  extraction_id STRING NOT NULL,
  field_path STRING NOT NULL,
  action STRING NOT NULL,
  reviewer STRING NOT NULL,
  decided_at TIMESTAMP NOT NULL,
  previous_status STRING NOT NULL,
  previous_value STRING NOT NULL,
  corrected_value STRING,
  note STRING,
  CONSTRAINT valid_correction_action
    CHECK (action IN ('confirm', 'correct', 'dispute')),
  CONSTRAINT valid_previous_status
    CHECK (previous_status IN ('pending', 'confirmed', 'disputed', 'corrected'))
) USING DELTA
TBLPROPERTIES ('delta.appendOnly' = 'true');
