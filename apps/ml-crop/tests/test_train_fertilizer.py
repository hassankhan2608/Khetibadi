from pathlib import Path
from typing import Any, cast

from scripts.train_fertilizer import (
    DEFAULT_HUMIDITY,
    DEFAULT_MOISTURE,
    FEATURES,
    load_dataset,
    train,
)


def test_train_fertilizer_emits_metadata(tmp_path: Path) -> None:
    dataset_path = tmp_path / "fertilizer_recommendation.csv"
    rows = [
        ",".join(
            [
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
            ],
        ),
    ]
    for index in range(12):
        rows.append(f"Clay,6.5,30,{45 + index},30,35,25,70,900,Rice,Urea")
        rows.append(f"Sandy,7.1,20,35,{42 + index},30,30,55,500,Wheat,DAP")
        rows.append(f"Loamy,6.8,25,40,35,{45 + index},28,60,700,Maize,MOP")
    dataset_path.write_text("\n".join(rows), encoding="utf-8")

    frame = load_dataset(dataset_path)
    artifact = train(frame, dataset_path, "local-test")

    metadata = cast(dict[str, Any], artifact["metadata"])
    assert metadata["features"] == FEATURES
    assert metadata["dataset_rows"] == 36
    assert metadata["random_state"] == 42
    assert set(metadata["classes"]) == {"DAP", "MOP", "Urea"}
    assert metadata["train_accuracy"] >= metadata["test_accuracy"]
    assert metadata["test_balanced_accuracy"] >= 0.9
    assert metadata["imputed_features"]["humidity"] == DEFAULT_HUMIDITY
    assert metadata["diagnostics"]["decision"] in {"ok", "review"}
    assert "dataset_sha256" in metadata
    assert artifact["model"] is not None


def test_load_fertilizer_accepts_western_maharashtra_kaggle_schema(tmp_path: Path) -> None:
    dataset_path = tmp_path / "Crop and fertilizer dataset.csv"
    rows = [
        "District_Name,Soil_color,Nitrogen,Phosphorus,Potassium,pH,Rainfall,"
        "Temperature,Crop,Fertilizer,Link",
        "Kolhapur,Black,75,50,100,6.5,1000,20,Sugarcane,Urea,https://example.test",
        "Pune,Red,35,45,80,7.1,700,28,Wheat,DAP,https://example.test",
    ]
    dataset_path.write_text("\n".join(rows), encoding="utf-8")

    frame = load_dataset(dataset_path)

    assert frame.columns.tolist() == [*FEATURES, "fertilizer"]
    assert frame["soil_type"].tolist() == ["black", "red"]
    assert frame["crop"].tolist() == ["sugarcane", "wheat"]
    assert frame["humidity"].tolist() == [DEFAULT_HUMIDITY, DEFAULT_HUMIDITY]
    assert frame["moisture"].tolist() == [DEFAULT_MOISTURE, DEFAULT_MOISTURE]
