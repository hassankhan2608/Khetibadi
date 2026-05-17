# Change Proposal: No-Mock Model, Data, Integration, and Verification Readiness

## ID: no-mock-model-data-readiness
## Status: Draft
## Date: 2026-05-24

## Why

The current stack is a verified runnable vertical slice, but several services still use
in-memory state, seeded demo rows, or explicit dev fallback modes. The user now wants
the project to move from runnable demo behaviour toward a real implementation where
models, training data, weather, and market integrations are wired through reproducible
pipelines and environment keys rather than mock responses.

This change defines the work required so the app can run with real artifacts once the
operator supplies API keys and dataset/model paths, while keeping large datasets and
trained model artifacts out of git.

## What Changes

- Deeply verify the approved UI/auth refresh work with Playwright before moving on.
- Inventory every current stub/mock/in-memory point and map it to the authoritative
  OpenSpec requirement it does not yet satisfy.
- Add reproducible ML data preparation and training scripts for crop, yield,
  fertilizer, and vision models.
- Add model metadata and startup validation so ML services use real artifacts by
  default and only enter fallback mode when explicitly requested for local dev.
- Wire weather through OpenWeatherMap using `OPENWEATHERMAP_API_KEY`.
- Wire market ingestion through a real mandi-price source using env-provided API key
  and resource endpoint/config.
- Expand automated tests for auth/UI flows, ML schemas/training utilities, and
  integration boundaries.
- Write a full README covering setup, env keys, dataset locations, training, model
  artifacts, Docker, test commands, and production/development modes.
- Produce an implementation-vs-OpenSpec checklist.

## Non-goals

- Large datasets and model binaries will not be committed to git.
- If a third-party data source requires an API key or terms acceptance, this change
  will document the exact env key/config and fail clearly until the operator provides it.
- This change does not weaken auth cookie or HMAC security to make local testing easier.

## Required Operator Inputs

- `OPENWEATHERMAP_API_KEY` for farm weather.
- A market/mandi data source configuration, preferably data.gov.in/AGMARKNET:
  - `DATA_GOV_IN_API_KEY`
  - `MARKET_DATA_RESOURCE_ID` or `MARKET_DATA_API_URL`
  - optional `MARKET_DATA_FORMAT=json`
- Local dataset paths or download credentials/URLs for:
  - crop recommendation tabular dataset
  - crop yield dataset
  - fertilizer recommendation dataset
  - PlantVillage or approved plant disease image dataset
- Optional `GROQ_API_KEY` for real AI chat responses.

## Verification Requirements

- Playwright browser verification for login, register, refresh on reload, logout, farm,
  crop advisor, disease scan, market, and AI assistant.
- Unit tests for new training/data utilities.
- Service lint/type-check/build/tests for Go, Python, and TypeScript.
- Docker Compose startup verification.
- OpenSpec comparison report documenting complete, partial, and still-missing items.
