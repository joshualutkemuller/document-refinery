-- Gate S: canonical, bitemporal collateral portfolio limits.
--
-- Promoted from validated limit[i].* silver rows of a collateral_rule_schedule
-- document (see application/limit_promotion.py). Captures a cap on a dimension
-- (sector, credit quality, asset type, issuer, country, currency, ...), optionally
-- scoped to one value, stated as an absolute currency amount OR a relative percent,
-- measured on a valuation basis (market vs post-haircut value) at an aggregation
-- level. Every value carries silver lineage (Locked Decision 1) and requires owner
-- Gate S approval before deployment.

CREATE TABLE IF NOT EXISTS refinery.gold_collateral_limits (
  dimension STRING NOT NULL,          -- sector | credit_quality | asset_type | ...
  scope_value STRING,                 -- specific value capped (e.g. 'Technology'); NULL = blanket
  limit_value DOUBLE NOT NULL,
  limit_unit STRING NOT NULL,         -- percent | absolute
  limit_currency STRING,              -- required when limit_unit = 'absolute'
  basis STRING,                       -- market_value | post_haircut_value | notional | par
  aggregation STRING,                 -- posted_collateral | portfolio | per_issuer | ...
  counterparty STRING,
  agreement_id STRING,
  schedule_version STRING,
  clearing_house STRING,
  valid_from DATE,
  valid_to DATE,
  knowledge_from TIMESTAMP NOT NULL,
  knowledge_to TIMESTAMP,
  silver_extraction_ids ARRAY<STRING> NOT NULL,
  doc_id STRING NOT NULL,
  CONSTRAINT valid_limit_unit CHECK (limit_unit IN ('percent', 'absolute')),
  CONSTRAINT valid_percent_limit CHECK (
    limit_unit <> 'percent' OR limit_value BETWEEN 0.0 AND 100.0
  ),
  CONSTRAINT valid_absolute_limit CHECK (
    limit_unit <> 'absolute' OR (limit_value >= 0.0 AND limit_currency IS NOT NULL)
  ),
  CONSTRAINT valid_limit_valid_time CHECK (valid_to IS NULL OR valid_from <= valid_to),
  CONSTRAINT valid_limit_knowledge_time CHECK (
    knowledge_to IS NULL OR knowledge_from <= knowledge_to
  )
) USING DELTA;
