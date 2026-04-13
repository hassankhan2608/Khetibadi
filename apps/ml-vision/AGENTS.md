# AGENTS.md — apps/ml-vision

> Python/FastAPI service. Port 8011. Plant disease detection via ResNet34 + OpenCV pipeline.
> Read root AGENTS.md first, then this file.

## Service Responsibility

Accepts plant leaf images, runs background removal (rembg), OpenCV preprocessing,
and ResNet34 inference. Returns disease class, confidence, and annotated image.

Owns:
- `resnet34_plantvillage.pth` (38-class PlantVillage fine-tune)
- OpenCV preprocessing pipeline
- Async job result cache in Redis (`vision:result:<job_id>`, TTL 1h)

## Layout

```
apps/ml-vision/
├── app/
│   ├── main.py                 # FastAPI app + lifespan model loader
│   ├── routes/
│   │   ├── detect.py           # POST /ml/vision/detect (sync)
│   │   ├── detect_async.py     # POST /ml/vision/detect/async + GET /ml/vision/detect/:job_id
│   │   └── classes.py          # GET /ml/vision/classes
│   ├── services/
│   │   ├── background_removal.py  # rembg wrapper with fallback
│   │   ├── preprocessing.py       # OpenCV pipeline
│   │   └── inference.py           # ResNet34 forward pass
│   ├── schemas/
│   │   └── vision.py
│   └── middleware/
│       └── hmac_auth.py
├── models/                     # *.pth files — gitignored
├── scripts/
│   ├── preprocess_bg_remove.py # rembg batch preprocessing for PlantVillage
│   └── train_vision.py         # ResNet34 fine-tuning
├── tests/
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

## Preprocessing Pipeline (FIXED ORDER — do not reorder)

1. `rembg.remove(image_bytes)` → white background composite (fallback: skip if exception)
2. RGB → LAB color space
3. Otsu threshold on L channel
4. Morphological opening then closing
5. Distance transform
6. Canny edge detection
7. Find contours → bounding box of largest contour
8. Crop + resize to 128×128 (fallback: full resize if no contour)
9. Normalize with ImageNet mean/std
10. ResNet34 forward pass

**Do NOT change this pipeline without running the full PlantVillage validation set first.**

## Key Invariants

- **Confidence threshold:** 0.60. Below this → `disease: "uncertain"`, `is_healthy: false`.
- **rembg fallback:** if `rembg` raises ANY exception, log WARN and continue with original image.
  Set `background_removed: false` in response. Never return 5xx for rembg failure.
- **No contour fallback:** if no contour found, use full 128×128 resize. Set `fallback_resize: true`.
- **Input limits:** JPG/PNG only, max 10MB, min 64×64 pixels.
- **Async jobs:** result stored in Redis as `vision:result:<job_id>` with 1h TTL.
- **Training seed:** `torch.manual_seed(42)` always set in training scripts.

## Critical Pitfalls

- **NEVER** change the OpenCV pipeline order without revalidating on PlantVillage.
- **NEVER** commit `.pth` files.
- **NEVER** return 5xx when rembg fails — it is a soft dependency.
- **NEVER** skip input validation before passing to OpenCV (corrupt images will crash cv2.imdecode).

## Dev Commands

```bash
cd apps/ml-vision
uv run uvicorn app.main:app --reload --port 8011
uv run pytest tests/ -v
uv run ruff check .
uv run mypy .
# Preprocess PlantVillage dataset (run once before training):
uv run python scripts/preprocess_bg_remove.py
# Train:
uv run python scripts/train_vision.py
```

## Spec Reference

`openspec/specs/ml-vision/spec.md`
