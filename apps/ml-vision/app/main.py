"""FastAPI entrypoint for plant disease detection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from uuid import uuid4

import torch
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from torch import nn
from torchvision import models, transforms

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ml-vision"
REPLAY_WINDOW_SECONDS = 300
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_SIDE = 64
JOB_TTL_SECONDS = 3600
IMAGE_SIZE = 224
OOD_IMAGE_SIZE = 96
MIN_PLANT_PIXEL_RATIO = 0.03
MIN_AMBIGUOUS_PLANT_RATIO = 0.08
MIN_EDGE_RATIO = 0.015
MIN_MEAN_SATURATION = 0.06

logger = logging.getLogger(SERVICE_NAME)


class AuthUser(BaseModel):
    user_id: str


class ImageMetadata(BaseModel):
    filename: str
    content_type: str
    width: int
    height: int
    size_bytes: int


class DiseaseDetection(BaseModel):
    disease: str
    confidence: float
    is_healthy: bool
    background_removed: bool
    fallback_resize: bool
    annotated_image_base64: str
    model_mode: Literal["model", "stub"]
    warning: str | None
    metadata: ImageMetadata


class VisionArtifact(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    model: Any
    classes: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PlantImageAssessment:
    plant_pixel_ratio: float
    edge_ratio: float
    mean_saturation: float
    plant_like: bool


class DetectionJob(BaseModel):
    job_id: str
    status: Literal["queued", "completed", "failed"]
    submitted_at: datetime
    expires_at: datetime
    result: DiseaseDetection | None = None
    error: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    load_artifact(settings)
    logger.info(
        "service starting",
        extra={"service": SERVICE_NAME, "env": settings.app_env, "port": settings.port},
    )
    try:
        yield
    finally:
        logger.info("service stopped cleanly", extra={"service": SERVICE_NAME})


app = FastAPI(title="khetibadi-ml-vision", lifespan=lifespan)
jobs: dict[str, DetectionJob] = {}
vision_artifact: VisionArtifact | None = None


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
    artifact_present = Path(settings.vision_model_path).exists()
    loaded = vision_artifact is not None
    mode = "model" if loaded else "stub"
    if loaded and vision_artifact is not None:
        classes = vision_artifact.classes
    else:
        classes = supported_classes()
    return {
        "status": "ok" if loaded or settings.ml_allow_stub_mode else "degraded",
        "service": SERVICE_NAME,
        "model_mode": mode,
        "model_artifact_present": artifact_present,
        "model_loaded": loaded,
        "classes": classes,
        "cuda_available": torch.cuda.is_available(),
    }


@app.post("/ml/vision/detect")
async def detect_disease(
    _: AuthDependency,
    image: Annotated[UploadFile, File()],
    async_mode: Annotated[bool, Query(alias="async")] = False,
) -> DiseaseDetection | dict[str, str]:
    if async_mode:
        return await create_detection_job(image)
    image_bytes = await read_image(image)
    return build_detection(image, image_bytes)


@app.post("/ml/vision/detect/async", status_code=status.HTTP_202_ACCEPTED)
async def detect_disease_async(
    _: AuthDependency,
    image: Annotated[UploadFile, File()],
) -> dict[str, str]:
    return await create_detection_job(image)


@app.get("/ml/vision/detect/{job_id}")
async def get_detection_job(job_id: str, _: AuthDependency) -> DetectionJob:
    prune_expired_jobs()
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "detection job not found"},
        )
    return job


@app.get("/ml/vision/jobs/{job_id}")
async def get_detection_job_alias(job_id: str, user: AuthDependency) -> DetectionJob:
    return await get_detection_job(job_id, user)


@app.get("/ml/vision/classes")
async def disease_classes(_: AuthDependency) -> dict[str, list[str]]:
    if vision_artifact is not None:
        return {"classes": vision_artifact.classes}
    return {"classes": supported_classes()}


async def create_detection_job(image: UploadFile) -> dict[str, str]:
    image_bytes = await read_image(image)
    job_id = str(uuid4())
    submitted_at = datetime.now(UTC)
    jobs[job_id] = DetectionJob(
        job_id=job_id,
        status="completed",
        submitted_at=submitted_at,
        expires_at=submitted_at + timedelta(seconds=JOB_TTL_SECONDS),
        result=build_detection(image, image_bytes),
    )
    return {"job_id": job_id, "status": "completed"}


def load_artifact(settings: Settings) -> None:
    global vision_artifact
    path = Path(settings.vision_model_path)
    if path.exists():
        vision_artifact = load_vision_artifact(path)
        logger.info(
            "vision model artifact loaded",
            extra={"path": str(path), "classes": len(vision_artifact.classes)},
        )
        return
    vision_artifact = None
    if settings.ml_allow_stub_mode:
        logger.warning("vision model artifact missing; explicit stub mode enabled")
        return
    msg = f"vision model artifact is not available: {path}"
    raise RuntimeError(msg)


def load_vision_artifact(path: Path) -> VisionArtifact:
    checkpoint = cast(dict[str, Any], torch.load(path, map_location="cpu", weights_only=False))
    state_dict = checkpoint.get("state_dict")
    classes = checkpoint.get("classes")
    metadata = checkpoint.get("metadata")
    if (
        not isinstance(state_dict, dict)
        or not isinstance(classes, list)
        or not isinstance(metadata, dict)
    ):
        msg = "vision checkpoint must contain state_dict, classes, and metadata"
        raise ValueError(msg)
    class_names = [str(item) for item in classes]
    if len(class_names) < 2:
        msg = "vision checkpoint must contain at least two classes"
        raise ValueError(msg)
    model = create_resnet34(len(class_names))
    model.load_state_dict(state_dict)
    model.eval()
    return VisionArtifact(model=model, classes=class_names, metadata=metadata)


def create_resnet34(num_classes: int) -> nn.Module:
    model = cast(nn.Module, models.resnet34(weights=None))
    classifier = cast(nn.Linear, model.fc)
    model.fc = nn.Linear(classifier.in_features, num_classes)
    return model


async def read_image(image: UploadFile) -> bytes:
    content = await image.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": "payload_too_large", "message": "image must be at most 10MB"},
        )
    if not is_supported_image(content):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"error": "unsupported_media_type", "message": "image must be JPG or PNG"},
        )
    return content


def build_detection(image: UploadFile, image_bytes: bytes) -> DiseaseDetection:
    artifact = vision_artifact
    metadata = inspect_image(image, image_bytes)
    assessment = assess_plant_likelihood(image_bytes)
    if not assessment.plant_like:
        model_mode: Literal["model", "stub"] = "model" if artifact is not None else "stub"
        return non_plant_detection(image_bytes, metadata, model_mode)
    if artifact is not None:
        return predict_detection(image_bytes, metadata, artifact)
    ensure_stub_available()
    digest = hashlib.sha256(image_bytes).hexdigest()
    classes = supported_classes()
    disease = classes[int(digest[:8], 16) % len(classes)]
    confidence = 0.52 + ((int(digest[8:10], 16) % 40) / 100)
    settings = get_settings()
    if confidence < settings.confidence_threshold:
        disease = "uncertain"
        is_healthy = False
    else:
        is_healthy = "healthy" in disease
    return DiseaseDetection(
        disease=disease,
        confidence=round(min(confidence, 0.98), 2),
        is_healthy=is_healthy,
        background_removed=False,
        fallback_resize=metadata.width < 128 or metadata.height < 128,
        annotated_image_base64=encode_image(image_bytes),
        model_mode="stub",
        warning="model_artifact_missing",
        metadata=metadata,
    )


def inspect_image(image: UploadFile, image_bytes: bytes) -> ImageMetadata:
    try:
        with Image.open(BytesIO(image_bytes)) as opened:
            width, height = opened.size
            image_format = opened.format or "unknown"
            opened.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_image", "message": "image could not be decoded"},
        ) from exc
    if width < MIN_IMAGE_SIDE or height < MIN_IMAGE_SIDE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "image_too_small", "message": "image must be at least 64x64"},
        )
    return ImageMetadata(
        filename=image.filename or "upload",
        content_type=image.content_type or f"image/{image_format.lower()}",
        width=width,
        height=height,
        size_bytes=len(image_bytes),
    )


def predict_detection(
    image_bytes: bytes,
    metadata: ImageMetadata,
    artifact: VisionArtifact,
) -> DiseaseDetection:
    tensor = preprocess_image(image_bytes)
    model = cast(nn.Module, artifact.model)
    with torch.no_grad():
        logits = model(tensor.unsqueeze(0))
        scores = torch.softmax(logits.squeeze(0), dim=0)
    class_id = int(scores.argmax().item())
    confidence = float(scores[class_id].item())
    settings = get_settings()
    disease = artifact.classes[class_id]
    if confidence < settings.confidence_threshold:
        disease = "uncertain"
        is_healthy = False
    else:
        is_healthy = "healthy" in disease.lower()
    return DiseaseDetection(
        disease=disease,
        confidence=round(confidence, 4),
        is_healthy=is_healthy,
        background_removed=False,
        fallback_resize=metadata.width < IMAGE_SIZE or metadata.height < IMAGE_SIZE,
        annotated_image_base64=encode_image(image_bytes),
        model_mode="model",
        warning=None,
        metadata=metadata,
    )


def assess_plant_likelihood(image_bytes: bytes) -> PlantImageAssessment:
    with Image.open(BytesIO(image_bytes)) as opened:
        hsv_image = opened.convert("RGB").resize((OOD_IMAGE_SIZE, OOD_IMAGE_SIZE)).convert("HSV")
    flatten = getattr(hsv_image, "get_flattened_data", None)
    pixels = list(flatten()) if callable(flatten) else list(hsv_image.getdata())
    total = len(pixels)
    if total == 0:
        return PlantImageAssessment(
            plant_pixel_ratio=0,
            edge_ratio=0,
            mean_saturation=0,
            plant_like=False,
        )
    plant_pixels = 0
    saturation_sum = 0.0
    luminance: list[float] = []
    for hue_raw, saturation_raw, value_raw in pixels:
        hue = (hue_raw / 255) * 360
        saturation = saturation_raw / 255
        value = value_raw / 255
        saturation_sum += saturation
        luminance.append(value)
        is_green = 55 <= hue <= 165 and saturation >= 0.18 and value >= 0.12
        is_dry_leaf = 18 <= hue < 55 and saturation >= 0.15 and value >= 0.18
        if is_green or is_dry_leaf:
            plant_pixels += 1
    plant_ratio = plant_pixels / total
    edge_ratio = luminance_edge_ratio(luminance, OOD_IMAGE_SIZE)
    mean_saturation = saturation_sum / total
    plant_like = (
        plant_ratio >= MIN_PLANT_PIXEL_RATIO
        and mean_saturation >= MIN_MEAN_SATURATION
        and (plant_ratio >= MIN_AMBIGUOUS_PLANT_RATIO or edge_ratio >= MIN_EDGE_RATIO)
    )
    return PlantImageAssessment(
        plant_pixel_ratio=plant_ratio,
        edge_ratio=edge_ratio,
        mean_saturation=mean_saturation,
        plant_like=plant_like,
    )


def luminance_edge_ratio(luminance: list[float], width: int) -> float:
    if width <= 1:
        return 0
    edge_pixels = 0
    comparisons = 0
    for y in range(width - 1):
        row = y * width
        next_row = (y + 1) * width
        for x in range(width - 1):
            index = row + x
            dx = abs(luminance[index] - luminance[index + 1])
            dy = abs(luminance[index] - luminance[next_row + x])
            if max(dx, dy) >= 0.10:
                edge_pixels += 1
            comparisons += 1
    if comparisons == 0:
        return 0
    return edge_pixels / comparisons


def non_plant_detection(
    image_bytes: bytes,
    metadata: ImageMetadata,
    model_mode: Literal["model", "stub"],
) -> DiseaseDetection:
    return DiseaseDetection(
        disease="not_plant",
        confidence=0,
        is_healthy=False,
        background_removed=False,
        fallback_resize=metadata.width < IMAGE_SIZE or metadata.height < IMAGE_SIZE,
        annotated_image_base64=encode_image(image_bytes),
        model_mode=model_mode,
        warning="non_plant_image",
        metadata=metadata,
    )


def preprocess_image(image_bytes: bytes) -> torch.Tensor:
    with Image.open(BytesIO(image_bytes)) as opened:
        image = opened.convert("RGB")
    transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )
    return cast(torch.Tensor, transform(image))


def ensure_stub_available() -> None:
    settings = get_settings()
    if Path(settings.vision_model_path).exists():
        return
    if settings.ml_allow_stub_mode:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"error": "model_unavailable", "message": "vision model artifact is not available"},
    )


def prune_expired_jobs() -> None:
    now = datetime.now(UTC)
    expired = [job_id for job_id, job in jobs.items() if job.expires_at <= now]
    for job_id in expired:
        del jobs[job_id]


def is_supported_image(content: bytes) -> bool:
    return content.startswith(b"\xff\xd8\xff") or content.startswith(b"\x89PNG\r\n\x1a\n")


def encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("ascii")


def supported_classes() -> list[str]:
    return [
        "apple_scab",
        "apple_black_rot",
        "apple_healthy",
        "corn_common_rust",
        "corn_healthy",
        "grape_black_rot",
        "grape_healthy",
        "potato_early_blight",
        "potato_late_blight",
        "potato_healthy",
        "tomato_bacterial_spot",
        "tomato_early_blight",
        "tomato_late_blight",
        "tomato_leaf_mold",
        "tomato_healthy",
        "uncertain",
    ]
