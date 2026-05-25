"""Train a ResNet34 PlantVillage classifier from an ImageFolder dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import torch
from torch import nn, optim
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import datasets, models, transforms
from torchvision.models import ResNet34_Weights

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_DIR = (
    REPO_ROOT / "data" / "kaggle" / "plantvillage-dataset" / "PlantVillage" / "raw"
)
DEFAULT_OUTPUT_PATH = REPO_ROOT / "apps" / "ml-vision" / "models" / "resnet34_plantvillage.pth"
RANDOM_SEED = 42
IMAGE_SIZE = 224
DEFAULT_EPOCHS = 3
DEFAULT_BATCH_SIZE = 16
DEFAULT_LEARNING_RATE = 1e-3


@dataclass(frozen=True)
class TrainResult:
    model: nn.Module
    classes: list[str]
    metadata: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--validation-split", type=float, default=0.2)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--freeze-backbone", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-pretrained", action="store_true")
    return parser.parse_args()


def train_from_image_folder(
    dataset_dir: Path,
    *,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    validation_split: float = 0.2,
    num_workers: int = 0,
    progress_every: int = 25,
    freeze_backbone: bool = True,
    pretrained: bool = True,
) -> TrainResult:
    torch.manual_seed(RANDOM_SEED)
    validate_dataset_dir(dataset_dir)

    weights = ResNet34_Weights.DEFAULT if pretrained else None
    train_base = datasets.ImageFolder(dataset_dir, transform=training_transforms())
    val_base = datasets.ImageFolder(dataset_dir, transform=inference_transforms())
    if len(train_base.classes) < 2:
        msg = "vision dataset must contain at least two class folders"
        raise ValueError(msg)

    train_dataset, val_dataset = split_dataset(train_base, val_base, validation_split)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )

    model = create_model(len(train_base.classes), weights=weights, freeze_backbone=freeze_backbone)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=learning_rate)

    history: list[dict[str, float]] = []
    for epoch in range(epochs):
        emit_progress(
            {
                "device": str(device),
                "epoch": epoch + 1,
                "epochs": epochs,
                "event": "epoch_start",
                "train_batches": len(train_loader),
                "val_batches": len(val_loader),
            }
        )
        started_at = time.monotonic()
        train_loss, train_accuracy = run_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device,
            epoch=epoch + 1,
            epochs=epochs,
            progress_every=progress_every,
        )
        emit_progress({"epoch": epoch + 1, "event": "validation_start"})
        val_loss, val_accuracy = evaluate(model, val_loader, criterion, device)
        duration_seconds = round(time.monotonic() - started_at, 2)
        history.append(
            {
                "epoch": float(epoch + 1),
                "train_loss": train_loss,
                "train_accuracy": train_accuracy,
                "val_loss": val_loss,
                "val_accuracy": val_accuracy,
            }
        )
        emit_progress(
            {
                "duration_seconds": duration_seconds,
                "epoch": epoch + 1,
                "event": "epoch_done",
                "train_accuracy": round(train_accuracy, 6),
                "train_loss": round(train_loss, 6),
                "val_accuracy": round(val_accuracy, 6),
                "val_loss": round(val_loss, 6),
            }
        )

    metadata = {
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset_dir": str(dataset_dir),
        "dataset_sha256": dataset_fingerprint(dataset_dir),
        "dataset_images": len(train_base),
        "classes": train_base.classes,
        "model_type": "torchvision.resnet34",
        "weights": "ResNet34_Weights.DEFAULT" if pretrained else "random",
        "image_size": IMAGE_SIZE,
        "random_seed": RANDOM_SEED,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "validation_split": validation_split,
        "freeze_backbone": freeze_backbone,
        "progress_every": progress_every,
        "history": history,
    }
    return TrainResult(model=model.cpu(), classes=list(train_base.classes), metadata=metadata)


def save_checkpoint(result: TrainResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": result.model.state_dict(),
            "classes": result.classes,
            "metadata": result.metadata,
        },
        output_path,
    )
    metadata_path = output_path.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(result.metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def create_model(
    num_classes: int,
    *,
    weights: ResNet34_Weights | None = ResNet34_Weights.DEFAULT,
    freeze_backbone: bool = False,
) -> nn.Module:
    model = cast(nn.Module, models.resnet34(weights=weights))
    if freeze_backbone:
        for parameter in model.parameters():
            parameter.requires_grad = False
    classifier = cast(nn.Linear, model.fc)
    in_features = classifier.in_features
    model.fc = nn.Linear(in_features, num_classes)
    return model


def training_transforms() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.75, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(mean=imagenet_mean(), std=imagenet_std()),
        ]
    )


def inference_transforms() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(mean=imagenet_mean(), std=imagenet_std()),
        ]
    )


def imagenet_mean() -> list[float]:
    return [0.485, 0.456, 0.406]


def imagenet_std() -> list[float]:
    return [0.229, 0.224, 0.225]


def split_dataset(
    train_base: datasets.ImageFolder,
    val_base: datasets.ImageFolder,
    validation_split: float,
) -> tuple[Dataset[Any], Dataset[Any]]:
    if not 0 < validation_split < 1:
        msg = "validation_split must be between 0 and 1"
        raise ValueError(msg)
    val_size = max(1, int(len(train_base) * validation_split))
    train_size = len(train_base) - val_size
    if train_size < 1:
        msg = "vision dataset needs at least one training image"
        raise ValueError(msg)
    generator = torch.Generator().manual_seed(RANDOM_SEED)
    indices = torch.randperm(len(train_base), generator=generator).tolist()
    train_indices = indices[:train_size]
    val_indices = indices[train_size:]
    return Subset(train_base, train_indices), Subset(val_base, val_indices)


def run_epoch(
    model: nn.Module,
    loader: DataLoader[Any],
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
    *,
    epoch: int,
    epochs: int,
    progress_every: int,
) -> tuple[float, float]:
    model.train()
    total_loss = 0.0
    correct = 0
    seen = 0
    total_batches = len(loader)
    for batch_index, (images, labels) in enumerate(loader, start=1):
        images = images.to(device)
        labels = labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        batch_size = labels.size(0)
        total_loss += float(loss.item()) * batch_size
        correct += int((logits.argmax(dim=1) == labels).sum().item())
        seen += batch_size
        if progress_every > 0 and (batch_index == 1 or batch_index % progress_every == 0):
            emit_progress(
                {
                    "accuracy": round(correct / max(seen, 1), 6),
                    "batch": batch_index,
                    "batches": total_batches,
                    "epoch": epoch,
                    "epochs": epochs,
                    "event": "train_batch",
                    "loss": round(total_loss / max(seen, 1), 6),
                }
            )
    return total_loss / max(seen, 1), correct / max(seen, 1)


def evaluate(
    model: nn.Module,
    loader: DataLoader[Any],
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    seen = 0
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            loss = criterion(logits, labels)
            batch_size = labels.size(0)
            total_loss += float(loss.item()) * batch_size
            correct += int((logits.argmax(dim=1) == labels).sum().item())
            seen += batch_size
    return total_loss / max(seen, 1), correct / max(seen, 1)


def validate_dataset_dir(dataset_dir: Path) -> None:
    if not dataset_dir.exists():
        msg = f"vision dataset directory not found: {dataset_dir}"
        raise FileNotFoundError(msg)
    class_dirs = [path for path in dataset_dir.iterdir() if path.is_dir()]
    if len(class_dirs) < 2:
        msg = "vision dataset must use ImageFolder layout with at least two class directories"
        raise ValueError(msg)


def dataset_fingerprint(dataset_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(dataset_dir.rglob("*")):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(dataset_dir)).encode())
        digest.update(file_sha256(path).encode())
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit_progress(payload: dict[str, object]) -> None:
    sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stderr.flush()


def main() -> None:
    args = parse_args()
    result = train_from_image_folder(
        cast(Path, args.dataset_dir),
        epochs=cast(int, args.epochs),
        batch_size=cast(int, args.batch_size),
        learning_rate=cast(float, args.learning_rate),
        validation_split=cast(float, args.validation_split),
        num_workers=cast(int, args.num_workers),
        progress_every=cast(int, args.progress_every),
        freeze_backbone=cast(bool, args.freeze_backbone),
        pretrained=not cast(bool, args.no_pretrained),
    )
    save_checkpoint(result, cast(Path, args.output))
    final_metrics = result.metadata["history"][-1]
    sys.stdout.write(
        json.dumps(
            {
                "output": str(args.output),
                "classes": len(result.classes),
                "val_accuracy": final_metrics["val_accuracy"],
            },
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
