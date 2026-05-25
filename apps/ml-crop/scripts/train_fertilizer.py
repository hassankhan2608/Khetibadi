"""Train the fertilizer recommendation model artifact."""

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
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

LOGGER = logging.getLogger("train-fertilizer")
RANDOM_STATE = 42
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_SOURCE = (
    "kaggle://sanchitagholap/crop-and-fertilizer-dataset-for-westernmaharashtra/"
    "Crop and fertilizer dataset.csv"
)
DEFAULT_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/Shanza-30/Fertilizer-Recommendation/"
    "main/fertilizer_recommendation.csv"
)
DEFAULT_DATASET_PATH = (
    REPO_ROOT / "data/kaggle/fertilizer-western-maharashtra/Crop and fertilizer dataset.csv"
)
DEFAULT_OUTPUT_PATH = REPO_ROOT / "apps/ml-crop/models/fertilizer_model.pkl"
NUMERIC_FEATURES = [
    "nitrogen",
    "phosphorus",
    "potassium",
    "temperature",
    "humidity",
    "moisture",
    "ph",
    "rainfall",
]
CATEGORICAL_FEATURES = ["soil_type", "crop"]
FEATURES = [*CATEGORICAL_FEATURES, *NUMERIC_FEATURES]
SOURCE_COLUMNS = [
    "Soil_Type",
    "Soil_pH",
    "Soil_Moisture",
    "Nitrogen_Level",
    "Phosphorus_Level",
    "Potassium_Level",
    "Temperature",
    "Humidity",
    "Rainfall",
    "Crop_Type",
    "Recommended_Fertilizer",
]
KAGGLE_COLUMNS = [
    "Soil_color",
    "Nitrogen",
    "Phosphorus",
    "Potassium",
    "pH",
    "Rainfall",
    "Temperature",
    "Crop",
    "Fertilizer",
]
DEFAULT_HUMIDITY = 50.0
DEFAULT_MOISTURE = 30.0


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
    LOGGER.info("wrote fertilizer model artifact to %s", args.output)


def ensure_dataset(path: Path, source_url: str, download: bool) -> Path:
    if path.exists():
        return path
    if not download:
        raise FileNotFoundError(f"dataset not found: {path}; rerun with --download")
    path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("downloading fertilizer dataset to %s", path)
    urlretrieve(source_url, path)
    return path


def load_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip() for column in frame.columns]
    frame = normalize_columns(frame)
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=[*FEATURES, "fertilizer"])
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].astype(str).str.strip().str.lower()
    frame["fertilizer"] = frame["fertilizer"].astype(str).str.strip()
    if frame.empty:
        raise ValueError("fertilizer dataset is empty after cleaning")
    return frame[[*FEATURES, "fertilizer"]]


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if all(column in frame.columns for column in SOURCE_COLUMNS):
        return normalize_rich_dataset(frame)
    if all(column in frame.columns for column in KAGGLE_COLUMNS):
        return normalize_western_maharashtra_dataset(frame)
    missing = [column for column in SOURCE_COLUMNS if column not in frame.columns]
    kaggle_missing = [column for column in KAGGLE_COLUMNS if column not in frame.columns]
    raise ValueError(
        "fertilizer dataset missing supported schema columns: "
        f"rich={missing}; western_maharashtra={kaggle_missing}",
    )


def normalize_rich_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame[SOURCE_COLUMNS].dropna()
    return frame.rename(
        columns={
            "Soil_Type": "soil_type",
            "Soil_pH": "ph",
            "Soil_Moisture": "moisture",
            "Nitrogen_Level": "nitrogen",
            "Phosphorus_Level": "phosphorus",
            "Potassium_Level": "potassium",
            "Temperature": "temperature",
            "Humidity": "humidity",
            "Rainfall": "rainfall",
            "Crop_Type": "crop",
            "Recommended_Fertilizer": "fertilizer",
        },
    )


def normalize_western_maharashtra_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame[KAGGLE_COLUMNS].dropna()
    normalized = frame.rename(
        columns={
            "Soil_color": "soil_type",
            "Nitrogen": "nitrogen",
            "Phosphorus": "phosphorus",
            "Potassium": "potassium",
            "Temperature": "temperature",
            "Rainfall": "rainfall",
            "Crop": "crop",
            "Fertilizer": "fertilizer",
            "pH": "ph",
        },
    )
    normalized["humidity"] = DEFAULT_HUMIDITY
    normalized["moisture"] = DEFAULT_MOISTURE
    return normalized


def train(frame: pd.DataFrame, dataset_path: Path, source_url: str) -> dict[str, object]:
    x = frame[FEATURES]
    y = frame["fertilizer"].astype(str)
    stratify = y if y.value_counts().min() >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=stratify,
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
        ],
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1),
            ),
        ],
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = float(accuracy_score(y_test, predictions))
    cv_accuracy = float(cross_val_score(model, x_train, y_train, cv=5, n_jobs=-1).mean())
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "dataset_source_url": source_url,
        "dataset_rows": int(len(frame)),
        "features": FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "classes": sorted(y.unique().tolist()),
        "model_type": "sklearn.pipeline.Pipeline(ColumnTransformer, RandomForestClassifier)",
        "random_state": RANDOM_STATE,
        "test_accuracy": accuracy,
        "cv_accuracy": cv_accuracy,
        "classification_report": report,
    }
    LOGGER.info(
        "fertilizer model metrics: %s",
        json.dumps({"accuracy": accuracy, "cv": cv_accuracy}),
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
