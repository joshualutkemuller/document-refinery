-- Gate S: canonical, bitemporal margin requirements (the demand side).
--
-- Promoted from validated requirement[i].* silver rows of a margin_requirement
-- document (see application/margin_promotion.py). Captures how much margin a
-- counterparty / netting set must post — e.g. an ISDA SIMM Initial Margin figure
-- or a Variation Margin call — which the optimizer must satisfy while respecting
-- the eligibility and limit constraints. Every value carries silver lineage
-- (Locked Decision 1) and requires owner Gate S approval before deployment.

CREATE TABLE IF NOT EXISTS refinery.gold_margin_requirements (
  counterparty STRING NOT NULL,
  agreement_id STRING,
  csa_schedule_ref STRING,
  netting_set_id STRING,
  margin_type STRING NOT NULL,        -- VM | IM | Repo | Clearing Fund | Secured Financing
  required_amount DOUBLE NOT NULL,
  currency STRING NOT NULL,
  risk_class STRING,
  model STRING,                       -- e.g. ISDA SIMM
  regulatory_regime STRING,
  valuation_date DATE,
  valid_from DATE,
  valid_to DATE,
  knowledge_from TIMESTAMP NOT NULL,
  knowledge_to TIMESTAMP,
  silver_extraction_ids ARRAY<STRING> NOT NULL,
  doc_id STRING NOT NULL,
  CONSTRAINT valid_required_amount CHECK (required_amount >= 0.0),
  CONSTRAINT valid_margin_valid_time CHECK (valid_to IS NULL OR valid_from <= valid_to),
  CONSTRAINT valid_margin_knowledge_time CHECK (
    knowledge_to IS NULL OR knowledge_from <= knowledge_to
  )
) USING DELTA;
