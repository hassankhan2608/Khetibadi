from pathlib import Path
from typing import Any, cast

from scripts.train_crop import FEATURES, load_dataset, train


def test_train_crop_emits_metadata(tmp_path: Path) -> None:
    dataset_path = tmp_path / "Crop_recommendation.csv"
    rows = ["N,P,K,temperature,humidity,ph,rainfall,label"]
    for index in range(10):
        rows.append(f"{80 + index},40,45,24,82,6.5,220,rice")
        rows.append(f"{35 + index},65,25,18,55,7.0,80,wheat")
    dataset_path.write_text("\n".join(rows), encoding="utf-8")

    frame = load_dataset(dataset_path)
    artifact = train(frame, dataset_path, "local-test")

    metadata = cast(dict[str, Any], artifact["metadata"])
    assert metadata["features"] == FEATURES
    assert metadata["dataset_rows"] == 20
    assert metadata["random_state"] == 42
    assert set(metadata["classes"]) == {"rice", "wheat"}
    assert metadata["train_accuracy"] >= metadata["test_accuracy"]
    assert metadata["test_balanced_accuracy"] >= 0.9
    assert metadata["diagnostics"]["underfit_warning"] is False
    assert metadata["diagnostics"]["decision"] in {"ok", "review"}
    assert "dataset_sha256" in metadata
    assert artifact["model"] is not None
