"""FastAPI entrypoint for crop, yield, and fertilizer recommendations."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import joblib
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ml-crop"
REPLAY_WINDOW_SECONDS = 300
MAX_BATCH_SIZE = 50

logger = logging.getLogger(SERVICE_NAME)


class CropArtifact(BaseModel):
    model: Any
    metadata: dict[str, Any]


class AuthUser(BaseModel):
    user_id: str


class CropFeatures(BaseModel):
    nitrogen: float = Field(ge=0, le=140)
    phosphorus: float = Field(ge=5, le=145)
    potassium: float = Field(ge=5, le=205)
    temperature: float = Field(ge=-10, le=55)
    humidity: float = Field(ge=0, le=100)
    ph: float = Field(ge=3.5, le=9.0)
    rainfall: float = Field(ge=0, le=3000)


class CropRecommendationRequest(CropFeatures):
    season: str = Field(default="kharif", min_length=1, max_length=40)
    state: str = Field(default="unknown", min_length=1, max_length=80)


class YieldPredictionRequest(CropFeatures):
    crop: str = Field(min_length=1, max_length=80)
    area_hectares: float = Field(gt=0, le=10000)
    season: str = Field(default="kharif", min_length=1, max_length=40)
    state: str = Field(default="unknown", min_length=1, max_length=80)
    district: str = Field(default="unknown", min_length=1, max_length=120)


class FertilizerRecommendationRequest(CropFeatures):
    crop: str = Field(min_length=1, max_length=80)
    soil_type: str = Field(default="loamy", min_length=1, max_length=40)
    moisture: float = Field(default=30, ge=0, le=100)


class BatchRecommendationRequest(BaseModel):
    records: list[CropRecommendationRequest] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class CropRecommendation(BaseModel):
    crop: str
    confidence: float
    alternatives: list[str]
    model_mode: Literal["model", "stub"]
    warning: str | None


class YieldPrediction(BaseModel):
    crop: str
    predicted_yield_tonnes: float
    yield_per_hectare_tonnes: float
    model_mode: Literal["model", "stub"]
    warning: str | None


class FertilizerRecommendation(BaseModel):
    recommendation: str
    nitrogen_kg_per_ha: float
    phosphorus_kg_per_ha: float
    potassium_kg_per_ha: float
    model_mode: Literal["model", "stub"]
    warning: str | None


crop_artifact: CropArtifact | None = None
yield_artifact: CropArtifact | None = None
fertilizer_artifact: CropArtifact | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    load_artifacts(settings)
    logger.info(
        "service starting",
        extra={"service": SERVICE_NAME, "env": settings.app_env, "port": settings.port},
    )
    try:
        yield
    finally:
        logger.info("service stopped cleanly", extra={"service": SERVICE_NAME})


app = FastAPI(title="khetibadi-ml-crop", lifespan=lifespan)


def require_hmac_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    x_hmac_signature: Annotated[str | None, Header(alias="X-HMAC-Signature")] = None,
    x_timestamp: Annotated[str | None, Header(alias="X-Timestamp")] = None,
) -> AuthUser:
    settings = get_settings()
    if settings.hmac_secret == "":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "service_unavailable", "message": "HMAC secret is not configured"},
        )
    if x_user_id is None or x_hmac_signature is None or x_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "missing HMAC identity headers"},
        )
    try:
        timestamp = int(x_timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "invalid timestamp"},
        ) from exc
    if abs(time.time() - timestamp) > REPLAY_WINDOW_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "replay_detected",
                "message": "request timestamp is outside replay window",
            },
        )
    expected = hmac.new(
        settings.hmac_secret.encode(),
        f"{x_user_id}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_hmac_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "invalid HMAC signature"},
        )
    return AuthUser(user_id=x_user_id)


AuthDependency = Annotated[AuthUser, Depends(require_hmac_user)]


@app.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    model_paths = [
        settings.crop_model_path,
        settings.yield_model_path,
        settings.fertilizer_model_path,
    ]
    artifacts_present = all(Path(path).exists() for path in model_paths)
    loaded_artifacts = {
        "crop": crop_artifact is not None,
        "yield": yield_artifact is not None,
        "fertilizer": fertilizer_artifact is not None,
    }
    mode = "model" if all(loaded_artifacts.values()) else "stub"
    return {
        "status": "ok" if artifacts_present or settings.ml_allow_stub_mode else "degraded",
        "service": SERVICE_NAME,
        "model_mode": mode,
        "model_artifacts_present": artifacts_present,
        "loaded_artifacts": loaded_artifacts,
    }


@app.post("/ml/crop/recommend")
async def recommend_crop(req: CropRecommendationRequest, _: AuthDependency) -> CropRecommendation:
    if crop_artifact is not None:
        return predict_crop_recommendation(req, crop_artifact)
    ensure_stub_available()
    return build_crop_recommendation(req)


@app.post("/ml/crop/recommend/batch")
async def recommend_batch(
    req: BatchRecommendationRequest,
    _: AuthDependency,
) -> dict[str, list[CropRecommendation]]:
    if crop_artifact is not None:
        return {
            "results": [
                predict_crop_recommendation(record, crop_artifact) for record in req.records
            ],
        }
    ensure_stub_available()
    return {"results": [build_crop_recommendation(record) for record in req.records]}


@app.post("/ml/crop/batch")
async def recommend_batch_alias(
    req: BatchRecommendationRequest,
    user: AuthDependency,
) -> dict[str, list[CropRecommendation]]:
    return await recommend_batch(req, user)


@app.post("/ml/yield/predict")
async def predict_yield(req: YieldPredictionRequest, _: AuthDependency) -> YieldPrediction:
    if yield_artifact is not None:
        return predict_yield_model(req, yield_artifact)
    ensure_stub_available()
    base = 1.8 + (req.rainfall / 1200) + ((req.ph - 5.5) * 0.2)
    nutrient_boost = (req.nitrogen + req.phosphorus + req.potassium) / 900
    yield_per_hectare = max(0.5, min(8.5, base + nutrient_boost))
    return YieldPrediction(
        crop=req.crop.strip().lower(),
        predicted_yield_tonnes=round(yield_per_hectare * req.area_hectares, 2),
        yield_per_hectare_tonnes=round(yield_per_hectare, 2),
        model_mode="stub",
        warning="model_artifact_missing",
    )


@app.post("/ml/crop/yield")
async def predict_yield_alias(req: YieldPredictionRequest, user: AuthDependency) -> YieldPrediction:
    return await predict_yield(req, user)


@app.post("/ml/fertilizer/recommend")
async def recommend_fertilizer(
    req: FertilizerRecommendationRequest,
    _: AuthDependency,
) -> FertilizerRecommendation:
    if fertilizer_artifact is not None:
        return predict_fertilizer_model(req, fertilizer_artifact)
    ensure_stub_available()
    nitrogen = max(0.0, 120 - req.nitrogen)
    phosphorus = max(0.0, 60 - req.phosphorus)
    potassium = max(0.0, 80 - req.potassium)
    recommendation = "balanced NPK application"
    if req.ph < 5.8:
        recommendation = "apply lime before balanced NPK application"
    elif req.ph > 8.0:
        recommendation = "apply organic matter and gypsum before NPK application"
    return FertilizerRecommendation(
        recommendation=recommendation,
        nitrogen_kg_per_ha=round(nitrogen, 1),
        phosphorus_kg_per_ha=round(phosphorus, 1),
        potassium_kg_per_ha=round(potassium, 1),
        model_mode="stub",
        warning="model_artifact_missing",
    )


@app.post("/ml/crop/fertilizer")
async def recommend_fertilizer_alias(
    req: FertilizerRecommendationRequest,
    user: AuthDependency,
) -> FertilizerRecommendation:
    return await recommend_fertilizer(req, user)


@app.get("/ml/crop/info")
async def crop_info(_: AuthDependency) -> dict[str, object]:
    if crop_artifact is not None:
        return {
            "service": SERVICE_NAME,
            "model_mode": "model",
            "generated_at": datetime.now(UTC).isoformat(),
            "supported_crops": crop_artifact.metadata.get("classes", supported_crops()),
            "features": crop_artifact.metadata.get("features", crop_features()),
            "metadata": crop_artifact.metadata,
        }
    return {
        "service": SERVICE_NAME,
        "model_mode": "stub",
        "generated_at": datetime.now(UTC).isoformat(),
        "supported_crops": supported_crops(),
        "features": crop_features(),
    }


@app.get("/ml/crop/feature-importance")
async def feature_importance(_: AuthDependency) -> dict[str, float]:
    if crop_artifact is not None:
        importances = crop_artifact.metadata.get("feature_importance")
        if isinstance(importances, dict):
            return {str(key): float(value) for key, value in importances.items()}
    return {
        "nitrogen": 0.18,
        "phosphorus": 0.13,
        "potassium": 0.13,
        "temperature": 0.15,
        "humidity": 0.11,
        "ph": 0.12,
        "rainfall": 0.18,
    }


def ensure_stub_available() -> None:
    settings = get_settings()
    paths = [settings.crop_model_path, settings.yield_model_path, settings.fertilizer_model_path]
    if all(Path(path).exists() for path in paths):
        return
    if settings.ml_allow_stub_mode:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"error": "model_unavailable", "message": "model artifacts are not available"},
    )


def load_artifacts(settings: Settings) -> None:
    global crop_artifact, fertilizer_artifact, yield_artifact

    crop_path = Path(settings.crop_model_path)
    crop_artifact = load_artifact(crop_path, crop_features(), settings.ml_allow_stub_mode)
    yield_artifact = load_artifact(
        Path(settings.yield_model_path),
        yield_features(),
        settings.ml_allow_stub_mode,
    )
    fertilizer_artifact = load_artifact(
        Path(settings.fertilizer_model_path),
        fertilizer_features(),
        settings.ml_allow_stub_mode,
    )
    if crop_artifact is not None:
        logger.info(
            "crop model loaded",
            extra={"service": SERVICE_NAME, "model_path": str(crop_path)},
        )
    if yield_artifact is not None:
        logger.info(
            "yield model loaded",
            extra={"service": SERVICE_NAME, "model_path": settings.yield_model_path},
        )
    if fertilizer_artifact is not None:
        logger.info(
            "fertilizer model loaded",
            extra={"service": SERVICE_NAME, "model_path": settings.fertilizer_model_path},
        )


def load_artifact(
    path: Path,
    expected_features: list[str],
    allow_stub: bool,
) -> CropArtifact | None:
    if path.exists():
        return load_model_artifact(path, expected_features)
    if not allow_stub:
        raise RuntimeError(f"model artifact not found: {path}")
    logger.warning(
        "model missing; explicit stub mode enabled",
        extra={"service": SERVICE_NAME, "model_path": str(path)},
    )
    return None


def load_model_artifact(path: Path, expected_features: list[str]) -> CropArtifact:
    loaded = joblib.load(path)
    if not isinstance(loaded, dict):
        raise RuntimeError("model artifact must be a dict")
    model = loaded.get("model")
    metadata = loaded.get("metadata")
    if model is None or not isinstance(metadata, dict):
        raise RuntimeError("model artifact missing model or metadata")
    features = metadata.get("features")
    if features != expected_features:
        raise RuntimeError("model feature order does not match service contract")
    return CropArtifact(model=model, metadata=metadata)


def predict_crop_recommendation(
    req: CropRecommendationRequest,
    artifact: CropArtifact,
) -> CropRecommendation:
    frame = pd.DataFrame([crop_feature_row(req)], columns=crop_features())
    model = artifact.model
    prediction = str(cast(Any, model).predict(frame)[0])
    probabilities = cast(Any, model).predict_proba(frame)[0]
    classes = [str(item) for item in cast(Any, model).classes_]
    scored = sorted(
        zip(classes, probabilities, strict=True),
        key=lambda item: item[1],
        reverse=True,
    )
    alternatives = [crop for crop, _ in scored if crop != prediction][:3]
    confidence = next((float(score) for crop, score in scored if crop == prediction), 0.0)
    return CropRecommendation(
        crop=prediction,
        confidence=round(confidence, 4),
        alternatives=alternatives,
        model_mode="model",
        warning=None,
    )


def predict_yield_model(req: YieldPredictionRequest, artifact: CropArtifact) -> YieldPrediction:
    frame = pd.DataFrame([yield_feature_row(req)], columns=yield_features())
    prediction = float(cast(Any, artifact.model).predict(frame)[0])
    yield_per_hectare = max(0.0, prediction)
    return YieldPrediction(
        crop=req.crop.strip().lower(),
        predicted_yield_tonnes=round(yield_per_hectare * req.area_hectares, 2),
        yield_per_hectare_tonnes=round(yield_per_hectare, 2),
        model_mode="model",
        warning=None,
    )


def predict_fertilizer_model(
    req: FertilizerRecommendationRequest,
    artifact: CropArtifact,
) -> FertilizerRecommendation:
    frame = pd.DataFrame([fertilizer_feature_row(req)], columns=fertilizer_features())
    recommendation = str(cast(Any, artifact.model).predict(frame)[0])
    nitrogen = max(0.0, 120 - req.nitrogen)
    phosphorus = max(0.0, 60 - req.phosphorus)
    potassium = max(0.0, 80 - req.potassium)
    return FertilizerRecommendation(
        recommendation=recommendation,
        nitrogen_kg_per_ha=round(nitrogen, 1),
        phosphorus_kg_per_ha=round(phosphorus, 1),
        potassium_kg_per_ha=round(potassium, 1),
        model_mode="model",
        warning=None,
    )


def crop_feature_row(req: CropFeatures) -> dict[str, float]:
    return {
        "nitrogen": req.nitrogen,
        "phosphorus": req.phosphorus,
        "potassium": req.potassium,
        "temperature": req.temperature,
        "humidity": req.humidity,
        "ph": req.ph,
        "rainfall": req.rainfall,
    }


def yield_feature_row(req: YieldPredictionRequest) -> dict[str, str | float]:
    return {
        "state": req.state.strip().lower(),
        "district": req.district.strip().lower(),
        "season": req.season.strip().lower(),
        "crop": req.crop.strip().lower(),
        "area_hectares": req.area_hectares,
    }


def fertilizer_feature_row(req: FertilizerRecommendationRequest) -> dict[str, str | float]:
    return {
        "soil_type": req.soil_type.strip().lower(),
        "crop": req.crop.strip().lower(),
        "nitrogen": req.nitrogen,
        "phosphorus": req.phosphorus,
        "potassium": req.potassium,
        "temperature": req.temperature,
        "humidity": req.humidity,
        "moisture": req.moisture,
        "ph": req.ph,
        "rainfall": req.rainfall,
    }


def build_crop_recommendation(req: CropRecommendationRequest) -> CropRecommendation:
    crops = supported_crops()
    score_input = f"{req.nitrogen}:{req.phosphorus}:{req.potassium}:{req.rainfall}:{req.state}"
    index = int(hashlib.sha256(score_input.encode()).hexdigest()[:8], 16) % len(crops)
    if req.rainfall > 1000 and req.humidity > 65:
        crop = "rice"
    elif req.rainfall < 500 and req.temperature > 25:
        crop = "millet"
    elif 6.0 <= req.ph <= 7.5 and req.nitrogen > 70:
        crop = "wheat"
    else:
        crop = crops[index]
    alternatives = [candidate for candidate in crops if candidate != crop][:3]
    confidence = 0.72 + ((index % 10) / 100)
    return CropRecommendation(
        crop=crop,
        confidence=round(min(confidence, 0.91), 2),
        alternatives=alternatives,
        model_mode="stub",
        warning="model_artifact_missing",
    )


def supported_crops() -> list[str]:
    return ["rice", "wheat", "maize", "cotton", "sugarcane", "millet", "pulses"]


def crop_features() -> list[str]:
    return [
        "nitrogen",
        "phosphorus",
        "potassium",
        "temperature",
        "humidity",
        "ph",
        "rainfall",
    ]


def yield_features() -> list[str]:
    return ["state", "district", "season", "crop", "area_hectares"]


def fertilizer_features() -> list[str]:
    return [
        "soil_type",
        "crop",
        "nitrogen",
        "phosphorus",
        "potassium",
        "temperature",
        "humidity",
        "moisture",
        "ph",
        "rainfall",
    ]
