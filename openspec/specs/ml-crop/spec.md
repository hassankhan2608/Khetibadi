# ML Crop Specification

## Purpose

Three ML inference services hosted on FastAPI: crop recommendation (Random Forest), yield prediction (Gradient Boosting), and fertilizer recommendation (Random Forest). All models are pre-trained and loaded at startup via joblib.

## Requirements

### Requirement: Crop Recommendation Inference

The system SHALL recommend the most suitable crop given soil and climate parameters.

#### Scenario: Valid prediction
- GIVEN inputs: N (kg/ha), P (kg/ha), K (kg/ha), temperature (°C), humidity (%), pH, rainfall (mm)
- WHEN `POST /ml/crop/recommend` is called with all 7 features
- THEN the response includes:
  - `crop`: predicted crop name
  - `confidence`: model probability for top prediction (0.0–1.0)
  - `top_3`: list of top-3 crop names with probabilities
- AND the response is returned in under 200ms

#### Scenario: Out-of-range input
- GIVEN pH = 15 (valid range: 3.5–9.0)
- WHEN the endpoint is called
- THEN `422 Unprocessable Entity` is returned with:
  `{"field": "ph", "message": "must be between 3.5 and 9.0"}`

#### Scenario: Missing required field
- GIVEN the request body omits `rainfall`
- WHEN the endpoint is called
- THEN `422 Unprocessable Entity` is returned with field-level detail

#### Scenario: Model not loaded
- GIVEN the `.pkl` model file is missing at startup
- WHEN the service starts
- THEN startup fails with a clear log message: `"crop model file not found at <path>"`
- AND the service does not bind to port 8010

---

### Requirement: Yield Prediction Inference

The system SHALL predict crop yield in tonnes per hectare for a given crop, state, season, and area.

#### Scenario: Valid prediction
- GIVEN inputs: `crop`, `state`, `season` (Kharif/Rabi/Whole Year), `area_ha`
- WHEN `POST /ml/yield/predict` is called
- THEN the response includes:
  - `predicted_yield_t_ha`: float, tonnes per hectare
  - `predicted_total_t`: `predicted_yield_t_ha * area_ha`
  - `confidence_interval`: `{lower, upper}` at 80% CI

#### Scenario: Unknown crop-state combination
- GIVEN a crop-state pair not seen in training data
- WHEN the endpoint is called
- THEN the model still returns a prediction (tree-based models extrapolate)
- AND a warning `"low_confidence": true` is included in the response when the input falls outside the training distribution

#### Scenario: Negative area
- GIVEN `area_ha = -5`
- WHEN the endpoint is called
- THEN `422 Unprocessable Entity` is returned

---

### Requirement: Fertilizer Recommendation Inference

The system SHALL recommend a fertilizer type given soil and crop information.

#### Scenario: Valid recommendation
- GIVEN inputs: `temperature`, `humidity`, `moisture`, `soil_type`, `crop_type`, `nitrogen`, `potassium`, `phosphorus`
- WHEN `POST /ml/fertilizer/recommend` is called
- THEN the response includes:
  - `fertilizer`: recommended fertilizer name (e.g. "Urea", "DAP", "10-26-26")
  - `confidence`: model probability
  - `alternatives`: top-3 alternatives with probabilities

#### Scenario: Unknown soil type
- GIVEN `soil_type = "martian"` (not in training categories)
- WHEN the endpoint is called
- THEN `422 Unprocessable Entity` is returned with `{"field": "soil_type", "message": "unrecognized value"}`

---

### Requirement: Model Health

The service SHALL expose the loaded model version and feature importance.

#### Scenario: Model info endpoint
- WHEN `GET /ml/crop/info` is called
- THEN the response includes:
  - `model_type`: "RandomForestClassifier"
  - `n_estimators`: integer
  - `training_accuracy`: float
  - `features`: ordered list of feature names

#### Scenario: Feature importance
- WHEN `GET /ml/crop/feature-importance` is called
- THEN a list of `{feature, importance}` objects is returned, sorted by importance descending

---

### Requirement: Batch Inference

The service SHALL support batch prediction for up to 50 records in a single request.

#### Scenario: Batch crop recommendation
- GIVEN a list of 10 soil/climate input objects
- WHEN `POST /ml/crop/recommend/batch` is called
- THEN a list of 10 recommendation objects is returned in the same order
- AND the total response time is under 500ms

#### Scenario: Batch size exceeded
- GIVEN a list of 51 records
- WHEN the batch endpoint is called
- THEN `422 Unprocessable Entity` with `{"error": "batch_limit_exceeded", "max": 50}`
