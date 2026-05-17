# ML Training Specification Delta

## Added Requirements

### Requirement: Reproducible Artifact Training

The system MUST provide reproducible scripts for creating every ML artifact used by
the inference services.

#### Scenario: Training emits metadata

- GIVEN a training script is run with an approved dataset path
- WHEN the model artifact is written
- THEN a sidecar metadata file is written with dataset path/hash, feature names,
  target names, model type, validation metrics, trained_at timestamp, and random seed
- AND the model artifact remains gitignored

#### Scenario: Missing dataset fails clearly

- GIVEN a required dataset path is not configured or does not exist
- WHEN a training script starts
- THEN it exits non-zero with a clear message naming the missing env var or path

### Requirement: Real Model Readiness

ML services MUST use real artifacts by default.

#### Scenario: Missing model in production mode

- GIVEN fallback mode is disabled
- WHEN a required model artifact is missing
- THEN service readiness reports degraded or unavailable
- AND inference requests fail with a clear `model_unavailable` error

#### Scenario: Explicit development fallback

- GIVEN fallback mode is explicitly enabled by env for local development
- WHEN artifacts are missing
- THEN the service may return marked fallback responses
- AND every response identifies the fallback mode so it cannot be mistaken for real inference
