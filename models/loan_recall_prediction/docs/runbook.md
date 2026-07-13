# Production Runbook

## Operating Schedule

The MVP runs as a daily batch score before the agreed market cut-off. Intraday scoring should be enabled only after event-driven data freshness controls are approved.

## Health Checks

- Source data freshness within tolerance.
- Expected open-loan record counts.
- Feature null, range, schema, and join-rate checks.
- Model artifact and feature set version availability.
- Prediction volume and probability distribution sanity checks.
- Alert volume within operational capacity.

## Safe Degradation

If a critical source is delayed or a data-quality gate fails, suppress alerts, mark predictions with a non-pass data quality status, and notify support and business owners.

## Rollback

Rollback requires loading the prior approved model artifact, prior feature definition version if needed, smoke testing prediction generation, and documenting the change event.
