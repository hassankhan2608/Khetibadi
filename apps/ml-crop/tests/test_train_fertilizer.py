from pathlib import Path
from typing import Any, cast

from scripts.train_fertilizer import FEATURES, load_dataset, train


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
    assert "dataset_sha256" in metadata
    assert artifact["model"] is not None
