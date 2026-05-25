"""Train the Indian crop yield prediction model artifact."""

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
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

LOGGER = logging.getLogger("train-yield")
RANDOM_STATE = 42
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_SOURCE = "kaggle://nikhilmahajan29/crop-production-statistics-india/APY.csv"
DEFAULT_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/ankitaS11/Crop-Yield-Prediction-in-India-using-ML/"
    "main/crop_production.csv"
)
DEFAULT_DATASET_PATH = REPO_ROOT / "data/kaggle/crop-production-statistics-india/APY.csv"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "apps/ml-crop/models/yield_model.pkl"
NUMERIC_FEATURES = ["area_hectares"]
CATEGORICAL_FEATURES = ["state", "district", "season", "crop"]
FEATURES = [*CATEGORICAL_FEATURES, *NUMERIC_FEATURES]
COLUMN_ALIASES = {
    "state": ["State_Name", "State"],
    "district": ["District_Name", "District"],
    "crop_year": ["Crop_Year"],
    "season": ["Season"],
    "crop": ["Crop"],
    "area_hectares": ["Area"],
    "production_tonnes": ["Production"],
    "yield_per_hectare_tonnes": ["Yield"],
}
OVERFIT_R2_GAP = 0.15
UNDERFIT_R2 = 0.45


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
    LOGGER.info("wrote yield model artifact to %s", args.output)


def ensure_dataset(path: Path, source_url: str, download: bool) -> Path:
    if path.exists():
        return path
    if not download:
        raise FileNotFoundError(f"dataset not found: {path}; rerun with --download")
    path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("downloading yield dataset to %s", path)
    urlretrieve(source_url, path)
    return path


def load_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip() for column in frame.columns]
    frame = normalize_columns(frame)
    frame["area_hectares"] = pd.to_numeric(frame["area_hectares"], errors="coerce")
    frame["production_tonnes"] = pd.to_numeric(frame["production_tonnes"], errors="coerce")
    if "yield_per_hectare_tonnes" in frame.columns:
        frame["yield_per_hectare_tonnes"] = pd.to_numeric(
            frame["yield_per_hectare_tonnes"],
            errors="coerce",
        )
    else:
        frame["yield_per_hectare_tonnes"] = frame["production_tonnes"] / frame["area_hectares"]
    frame = frame.dropna(subset=["area_hectares", "production_tonnes"])
    frame = frame[(frame["area_hectares"] > 0) & (frame["production_tonnes"] > 0)]
    frame = frame.dropna(subset=["yield_per_hectare_tonnes"])
    frame = frame[frame["yield_per_hectare_tonnes"].between(0.01, 80)]
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].astype(str).str.strip().str.lower()
    if frame.empty:
        raise ValueError("yield dataset is empty after cleaning")
    return frame[[*FEATURES, "yield_per_hectare_tonnes"]]


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    selected: dict[str, pd.Series] = {}
    missing: list[str] = []
    for canonical, aliases in COLUMN_ALIASES.items():
        source = next((alias for alias in aliases if alias in frame.columns), None)
        if source is None:
            if canonical == "yield_per_hectare_tonnes":
                continue
            missing.append("/".join(aliases))
            continue
        selected[canonical] = frame[source]
    if missing:
        raise ValueError(f"yield dataset missing columns: {missing}")
    return pd.DataFrame(selected).dropna()


def train(frame: pd.DataFrame, dataset_path: Path, source_url: str) -> dict[str, object]:
    x = frame[FEATURES]
    y = frame["yield_per_hectare_tonnes"]
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
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
            ("regressor", GradientBoostingRegressor(random_state=RANDOM_STATE)),
        ],
    )
    model.fit(x_train, y_train)
    train_predictions = model.predict(x_train)
    predictions = model.predict(x_test)
    train_r2 = float(r2_score(y_train, train_predictions))
    train_mae = float(mean_absolute_error(y_train, train_predictions))
    r2 = float(r2_score(y_test, predictions))
    mae = float(mean_absolute_error(y_test, predictions))
    cv_results = cross_validate(
        model,
        x_train,
        y_train,
        cv=5,
        n_jobs=-1,
        scoring={"r2": "r2", "neg_mae": "neg_mean_absolute_error"},
        return_train_score=True,
    )
    cv_r2 = float(cv_results["test_r2"].mean())
    cv_r2_std = float(cv_results["test_r2"].std())
    cv_train_r2 = float(cv_results["train_r2"].mean())
    cv_mae = float(-cv_results["test_neg_mae"].mean())
    cv_train_mae = float(-cv_results["train_neg_mae"].mean())
    train_validation_r2_gap = train_r2 - r2
    cv_train_validation_r2_gap = cv_train_r2 - cv_r2
    diagnostics = {
        "overfit_warning": train_validation_r2_gap > OVERFIT_R2_GAP
        or cv_train_validation_r2_gap > OVERFIT_R2_GAP,
        "underfit_warning": r2 < UNDERFIT_R2 or cv_r2 < UNDERFIT_R2,
        "train_validation_r2_gap": train_validation_r2_gap,
        "cv_train_validation_r2_gap": cv_train_validation_r2_gap,
        "decision": "ok"
        if r2 >= UNDERFIT_R2 and train_validation_r2_gap <= OVERFIT_R2_GAP
        else "review",
    }
    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "dataset_source_url": source_url,
        "dataset_rows": int(len(frame)),
        "features": FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "target": "yield_per_hectare_tonnes",
        "model_type": "sklearn.pipeline.Pipeline(ColumnTransformer, GradientBoostingRegressor)",
        "random_state": RANDOM_STATE,
        "train_r2": train_r2,
        "train_mae": train_mae,
        "test_r2": r2,
        "test_mae": mae,
        "cv_r2": cv_r2,
        "cv_r2_std": cv_r2_std,
        "cv_train_r2": cv_train_r2,
        "cv_mae": cv_mae,
        "cv_train_mae": cv_train_mae,
        "diagnostics": diagnostics,
    }
    LOGGER.info(
        "yield model metrics: %s",
        json.dumps(
            {
                "train_r2": train_r2,
                "test_r2": r2,
                "test_mae": mae,
                "cv_r2": cv_r2,
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
