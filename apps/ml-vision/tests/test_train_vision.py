from pathlib import Path

import torch
from PIL import Image
from torch import nn

from scripts.train_vision import (
    RANDOM_SEED,
    create_model,
    dataset_fingerprint,
    sample_image_features,
    save_checkpoint,
    train_from_image_folder,
)


def write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 128), color=color).save(path, format="PNG")


def test_train_vision_writes_checkpoint_metadata(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "plantvillage"
    for index in range(3):
        write_image(dataset_dir / "apple_healthy" / f"apple_{index}.png", (40, 160, 60))
        write_image(dataset_dir / "tomato_late_blight" / f"tomato_{index}.png", (160, 60, 40))

    result = train_from_image_folder(
        dataset_dir,
        epochs=1,
        batch_size=2,
        validation_split=0.33,
        freeze_backbone=True,
        pretrained=False,
    )
    output_path = tmp_path / "resnet34_plantvillage.pth"
    save_checkpoint(result, output_path)

    assert output_path.exists()
    assert result.classes == ["apple_healthy", "tomato_late_blight"]
    assert result.metadata["random_seed"] == RANDOM_SEED
    assert result.metadata["dataset_images"] == 6
    assert result.metadata["dataset_sha256"] == dataset_fingerprint(dataset_dir)
    assert len(result.metadata["history"]) == 1

    checkpoint = torch.load(output_path, map_location="cpu", weights_only=False)
    assert checkpoint["classes"] == result.classes
    assert "state_dict" in checkpoint


def test_create_model_replaces_classifier_head() -> None:
    model = create_model(3, weights=None, freeze_backbone=True)
    classifier = model.fc

    assert isinstance(classifier, nn.Linear)
    assert classifier.out_features == 3
    assert classifier.weight.requires_grad


def test_save_checkpoint_writes_ood_profile(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "plantvillage"
    negative_dir = tmp_path / "negative"
    for index in range(3):
        write_image(dataset_dir / "apple_healthy" / f"apple_{index}.png", (40, 160, 60))
        write_image(dataset_dir / "tomato_late_blight" / f"tomato_{index}.png", (160, 60, 40))
        write_image(negative_dir / "wall" / f"wall_{index}.png", (130, 80, 200))

    result = train_from_image_folder(
        dataset_dir,
        epochs=1,
        batch_size=2,
        validation_split=0.33,
        freeze_backbone=True,
        pretrained=False,
    )
    output_path = tmp_path / "resnet34_plantvillage.pth"
    save_checkpoint(result, output_path, negative_dir)

    assert output_path.with_suffix(".ood.json").exists()
    assert sample_image_features(negative_dir, limit_per_class=2)
