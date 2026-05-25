from pathlib import Path
from typing import Any, cast

from scripts.train_yield import FEATURES, load_dataset, train


def test_train_yield_emits_metadata(tmp_path: Path) -> None:
    dataset_path = tmp_path / "crop_production.csv"
    rows = ["State_Name,District_Name,Crop_Year,Season,Crop,Area,Production"]
    for index in range(30):
        rows.append(f"Punjab,Ludhiana,2020,Kharif,Rice,{100 + index},{300 + index * 2}")
        rows.append(f"Punjab,Ludhiana,2020,Rabi,Wheat,{120 + index},{260 + index * 2}")
    dataset_path.write_text("\n".join(rows), encoding="utf-8")

    frame = load_dataset(dataset_path)
    artifact = train(frame, dataset_path, "local-test")

    metadata = cast(dict[str, Any], artifact["metadata"])
    assert metadata["features"] == FEATURES
    assert metadata["dataset_rows"] == 60
    assert metadata["random_state"] == 42
    assert metadata["target"] == "yield_per_hectare_tonnes"
    assert "dataset_sha256" in metadata
    assert artifact["model"] is not None


def test_load_yield_accepts_kaggle_apy_schema(tmp_path: Path) -> None:
    dataset_path = tmp_path / "APY.csv"
    rows = ["State,District ,Crop,Crop_Year,Season,Area ,Production,Yield"]
    rows.append("Punjab,Ludhiana,Rice,2020,Kharif,100,300,3.0")
    rows.append("Punjab,Ludhiana,Wheat,2020,Rabi,120,240,2.0")
    dataset_path.write_text("\n".join(rows), encoding="utf-8")

    frame = load_dataset(dataset_path)

    assert frame.columns.tolist() == [*FEATURES, "yield_per_hectare_tonnes"]
    assert frame["state"].tolist() == ["punjab", "punjab"]
    assert frame["district"].tolist() == ["ludhiana", "ludhiana"]
    assert frame["yield_per_hectare_tonnes"].tolist() == [3.0, 2.0]
