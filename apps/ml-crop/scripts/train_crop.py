"""Train the crop recommendation model artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlretrieve

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report
from sklearn.model_selection import cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

LOGGER = logging.getLogger("train-crop")
RANDOM_STATE = 42
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_SOURCE = "kaggle://atharvaingle/crop-recommendation-dataset/Crop_recommendation.csv"
DEFAULT_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/vaishnavid0604/agriculture-portal/main/"
    "farmer/ML/crop_recommendation/Crop_recommendation.csv"
)
DEFAULT_DATASET_PATH = REPO_ROOT / "data/kaggle/crop-recommendation/Crop_recommendation.csv"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "apps/ml-crop/models/crop_model.pkl"
FEATURES = ["nitrogen", "phosphorus", "potassium", "temperature", "humidity", "ph", "rainfall"]
SOURCE_COLUMNS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
OVERFIT_ACCURACY_GAP = 0.08
UNDERFIT_ACCURACY = 0.75


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--source-url", default=DEFAULT_DATASET_SOURCE)
    parser.add_argument("--download-url", default=DEFAULT_DOWNLOAD_URL)
    parser.add_argument("--download", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    dataset_path = ensure_dataset(args.dataset, args.download_url, args.download)
    frame = load_dataset(dataset_path)
    artifact = train(frame, dataset_path, args.source_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    LOGGER.info("wrote crop model artifact to %s", args.output)


def ensure_dataset(path: Path, source_url: str, download: bool) -> Path:
    if path.exists():
        return path
    if not download:
        raise FileNotFoundError(f"dataset not found: {path}; rerun with --download")
    path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("downloading crop dataset to %s", path)
    urlretrieve(source_url, path)
    return path


def load_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    expected = [*SOURCE_COLUMNS, "label"]
    missing = [column for column in expected if column not in frame.columns]
    if missing:
        raise ValueError(f"crop dataset missing columns: {missing}")
    frame = frame[expected].dropna()
    frame = frame.rename(columns={"N": "nitrogen", "P": "phosphorus", "K": "potassium"})
    if frame.empty:
        raise ValueError("crop dataset is empty after cleaning")
    return frame


def train(frame: pd.DataFrame, dataset_path: Path, source_url: str) -> dict[str, object]:
    x = frame[FEATURES]
    y = frame["label"].astype(str)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y,
    )
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=100,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ],
    )
    model.fit(x_train, y_train)
    train_predictions = model.predict(x_train)
    predictions = model.predict(x_test)
    train_accuracy = float(accuracy_score(y_train, train_predictions))
    train_balanced_accuracy = float(balanced_accuracy_score(y_train, train_predictions))
    accuracy = float(accuracy_score(y_test, predictions))
    balanced_accuracy = float(balanced_accuracy_score(y_test, predictions))
    cv_results = cross_validate(
        model,
        x_train,
        y_train,
        cv=5,
        n_jobs=-1,
        scoring=["accuracy", "balanced_accuracy"],
        return_train_score=True,
    )
    cv_accuracy = float(cv_results["test_accuracy"].mean())
    cv_accuracy_std = float(cv_results["test_accuracy"].std())
    cv_balanced_accuracy = float(cv_results["test_balanced_accuracy"].mean())
    cv_train_accuracy = float(cv_results["train_accuracy"].mean())
    train_validation_gap = train_accuracy - accuracy
    cv_train_validation_gap = cv_train_accuracy - cv_accuracy
    diagnostics = {
        "overfit_warning": train_validation_gap > OVERFIT_ACCURACY_GAP
        or cv_train_validation_gap > OVERFIT_ACCURACY_GAP,
        "underfit_warning": accuracy < UNDERFIT_ACCURACY or cv_accuracy < UNDERFIT_ACCURACY,
        "train_validation_accuracy_gap": train_validation_gap,
        "cv_train_validation_accuracy_gap": cv_train_validation_gap,
        "decision": "ok"
        if accuracy >= UNDERFIT_ACCURACY and train_validation_gap <= OVERFIT_ACCURACY_GAP
        else "review",
    }
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
    classifier = model.named_steps["classifier"]
    feature_importance = {
        feature: float(score)
        for feature, score in zip(FEATURES, classifier.feature_importances_, strict=True)
    }
    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "dataset_source_url": source_url,
        "dataset_rows": int(len(frame)),
        "features": FEATURES,
        "classes": sorted(y.unique().tolist()),
        "model_type": "sklearn.pipeline.Pipeline(StandardScaler, RandomForestClassifier)",
        "random_state": RANDOM_STATE,
        "train_accuracy": train_accuracy,
        "train_balanced_accuracy": train_balanced_accuracy,
        "test_accuracy": accuracy,
        "test_balanced_accuracy": balanced_accuracy,
        "cv_accuracy": cv_accuracy,
        "cv_accuracy_std": cv_accuracy_std,
        "cv_balanced_accuracy": cv_balanced_accuracy,
        "cv_train_accuracy": cv_train_accuracy,
        "diagnostics": diagnostics,
        "classification_report": report,
        "feature_importance": feature_importance,
    }
    LOGGER.info(
        "crop model metrics: %s",
        json.dumps(
            {
                "train_accuracy": train_accuracy,
                "test_accuracy": accuracy,
                "cv_accuracy": cv_accuracy,
                "diagnostics": diagnostics,
            },
        ),
    )
    return {"model": model, "metadata": metadata}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
