# Architecture

```text
Source Systems
  -> Raw Data Layer
  -> Validated Historical Tables
  -> Feature Engineering Pipeline
  -> Offline/Online Feature Stores
  -> Training Pipeline
  -> Model Registry
  -> Batch Scoring / API Scoring
  -> Prediction Store, Dashboard, Alerts, Optimizer Inputs
  -> Outcome and Feedback Capture
  -> Monitoring and Retraining
```

## Design Principles

- Maintain point-in-time correctness for every feature.
- Separate model development, model validation, and production approval duties.
- Keep prediction generation separate from downstream intervention decisions.
- Log model version, feature set version, input freshness, reason codes, and user actions.
- Degrade safely when source data is delayed or incomplete.
