from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ml.raptormaps_classifier import (  # noqa: E402
    DEFAULT_CLASSIFIER_ARTIFACT,
    DEFAULT_IMAGE_SIZE,
    DEFAULT_RAPTORMAPS_ROOT,
    RAPTORMAPS_CLASSES,
    RaptorMapsRecord,
    build_model,
    class_distribution,
    image_to_tensor,
    load_raptormaps_records,
    require_torch,
    stratified_split,
)


class RaptorMapsTorchDataset:
    def __init__(self, records: list[RaptorMapsRecord], label_to_index: dict[str, int]) -> None:
        self.records = records
        self.label_to_index = label_to_index

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[Any, int]:
        record = self.records[index]
        return image_to_tensor(record.image_path), self.label_to_index[record.label]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a small supervised RaptorMaps classifier on ROCm/PyTorch.")
    parser.add_argument("--data-root", default=str(DEFAULT_RAPTORMAPS_ROOT), help="RaptorMaps InfraredSolarModules root.")
    parser.add_argument("--output", default=str(DEFAULT_CLASSIFIER_ARTIFACT), help="Model artifact path.")
    parser.add_argument(
        "--metrics-output",
        default="data/metrics/raptormaps_classifier_metrics.json",
        help="Metrics JSON output path.",
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-class", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, or a torch device string.")
    parser.add_argument(
        "--class-weight-power",
        type=float,
        default=0.5,
        help="Exponent applied to inverse-frequency class weights. 0 disables weighting; 1 is full inverse weighting.",
    )
    parser.add_argument(
        "--best-metric",
        choices=("macro_recall", "macro_f1", "weighted_f1", "accuracy", "loss"),
        default="macro_recall",
        help="Validation metric used to select the saved checkpoint.",
    )
    return parser.parse_args()


def resolve_device(torch: Any, requested: str) -> Any:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def hardware_metadata(torch: Any, device: Any) -> dict[str, Any]:
    cuda_available = bool(torch.cuda.is_available())
    metadata: dict[str, Any] = {
        "torch_version": torch.__version__,
        "torch_hip_version": getattr(torch.version, "hip", None),
        "cuda_api_available_for_rocm": cuda_available,
        "device": str(device),
    }
    if cuda_available:
        metadata["gpu_name"] = torch.cuda.get_device_name(0)
        metadata["device_count"] = torch.cuda.device_count()
        try:
            metadata["memory_allocated_bytes"] = torch.cuda.memory_allocated(0)
            metadata["memory_reserved_bytes"] = torch.cuda.memory_reserved(0)
        except RuntimeError:
            pass
    return metadata


def snapshot_state_dict(model: Any) -> dict[str, Any]:
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def metric_is_better(metric: str, score: float, best_score: float | None) -> bool:
    if best_score is None:
        return True
    if metric == "loss":
        return score < best_score
    return score > best_score


def validate_split_support(
    train_records: list[RaptorMapsRecord],
    val_records: list[RaptorMapsRecord],
) -> None:
    train_counts = Counter(record.label for record in train_records)
    val_counts = Counter(record.label for record in val_records)
    missing_train = [label for label in RAPTORMAPS_CLASSES if train_counts[label] == 0]
    missing_val = [label for label in RAPTORMAPS_CLASSES if val_counts[label] == 0]
    if missing_train or missing_val:
        details = {
            "missing_train": missing_train,
            "missing_validation": missing_val,
        }
        raise ValueError(f"Stratified split lost class support: {json.dumps(details, sort_keys=True)}")


def evaluate(model: Any, loader: Any, device: Any, num_classes: int) -> dict[str, Any]:
    torch, _nn = require_torch()
    model.eval()
    confusion = torch.zeros((num_classes, num_classes), dtype=torch.long)
    total_loss = 0.0
    criterion = torch.nn.CrossEntropyLoss()
    total = 0
    correct = 0
    started = time.perf_counter()

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            logits = model(images)
            loss = criterion(logits, labels)
            total_loss += float(loss.item()) * labels.numel()
            predictions = logits.argmax(dim=1)
            total += labels.numel()
            correct += int((predictions == labels).sum().item())
            for truth, predicted in zip(labels.cpu(), predictions.cpu(), strict=False):
                confusion[int(truth.item()), int(predicted.item())] += 1

    elapsed = max(time.perf_counter() - started, 0.001)
    per_class = []
    recalls = []
    f1_scores = []
    weighted_f1_total = 0.0
    for index, label in enumerate(RAPTORMAPS_CLASSES):
        tp = int(confusion[index, index].item())
        support = int(confusion[index, :].sum().item())
        predicted_total = int(confusion[:, index].sum().item())
        precision = tp / predicted_total if predicted_total else 0.0
        recall = tp / support if support else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        recalls.append(recall)
        f1_scores.append(f1)
        weighted_f1_total += f1 * support
        per_class.append(
            {
                "label": label,
                "support": support,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            }
        )

    return {
        "loss": round(total_loss / max(total, 1), 6),
        "accuracy": round(correct / max(total, 1), 6),
        "macro_recall": round(sum(recalls) / len(recalls), 6),
        "macro_f1": round(sum(f1_scores) / len(f1_scores), 6),
        "weighted_f1": round(weighted_f1_total / max(total, 1), 6),
        "samples_per_second": round(total / elapsed, 2),
        "per_class": per_class,
        "confusion_matrix": confusion.tolist(),
    }


def main() -> None:
    args = parse_args()
    torch, _nn = require_torch()
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    records = load_raptormaps_records(args.data_root)
    train_records, val_records = stratified_split(
        records=records,
        val_ratio=args.val_ratio,
        seed=args.seed,
        max_per_class=args.max_per_class,
    )
    validate_split_support(train_records, val_records)
    label_to_index = {label: index for index, label in enumerate(RAPTORMAPS_CLASSES)}
    device = resolve_device(torch, args.device)

    train_dataset = RaptorMapsTorchDataset(train_records, label_to_index)
    val_dataset = RaptorMapsTorchDataset(val_records, label_to_index)
    pin_memory = str(device).startswith("cuda")
    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
    )
    val_loader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=pin_memory,
    )

    model = build_model(num_classes=len(RAPTORMAPS_CLASSES)).to(device)
    train_counts = Counter(record.label for record in train_records)
    class_weights = torch.tensor(
        [
            (len(train_records) / max(train_counts[label], 1)) ** args.class_weight_power
            for label in RAPTORMAPS_CLASSES
        ],
        dtype=torch.float32,
        device=device,
    )
    if args.class_weight_power > 0:
        class_weights = class_weights / class_weights.mean()
    else:
        class_weights = torch.ones_like(class_weights)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)

    history = []
    best_score: float | None = None
    best_record: dict[str, Any] | None = None
    best_metrics: dict[str, Any] | None = None
    best_state_dict: dict[str, Any] | None = None
    started = time.perf_counter()
    print(json.dumps({"event": "hardware", **hardware_metadata(torch, device)}, sort_keys=True), flush=True)
    print(
        json.dumps(
            {
                "event": "dataset",
                "total_records": len(records),
                "train_records": len(train_records),
                "val_records": len(val_records),
                "class_distribution": class_distribution(records),
            },
            sort_keys=True,
        ),
        flush=True,
    )

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_started = time.perf_counter()
        train_loss = 0.0
        train_total = 0
        train_correct = 0
        for images, labels in train_loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            train_loss += float(loss.item()) * labels.numel()
            train_total += labels.numel()
            train_correct += int((logits.argmax(dim=1) == labels).sum().item())

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        val_metrics = evaluate(model, val_loader, device, len(RAPTORMAPS_CLASSES))
        epoch_elapsed = max(time.perf_counter() - epoch_started, 0.001)
        record = {
            "epoch": epoch,
            "train_loss": round(train_loss / max(train_total, 1), 6),
            "train_accuracy": round(train_correct / max(train_total, 1), 6),
            "train_samples_per_second": round(train_total / epoch_elapsed, 2),
            "val_accuracy": val_metrics["accuracy"],
            "val_macro_recall": val_metrics["macro_recall"],
            "val_macro_f1": val_metrics["macro_f1"],
            "val_weighted_f1": val_metrics["weighted_f1"],
            "val_loss": val_metrics["loss"],
        }
        score = float(val_metrics[args.best_metric])
        is_best = metric_is_better(args.best_metric, score, best_score)
        record["is_best"] = is_best
        if is_best:
            best_score = score
            best_record = dict(record)
            best_metrics = dict(val_metrics)
            best_state_dict = snapshot_state_dict(model)
        history.append(record)
        print(json.dumps({"event": "epoch", **record}, sort_keys=True), flush=True)

    last_metrics = evaluate(model, val_loader, device, len(RAPTORMAPS_CLASSES))
    if best_state_dict is None or best_metrics is None or best_record is None:
        best_state_dict = snapshot_state_dict(model)
        best_metrics = last_metrics
        best_record = {
            "epoch": args.epochs,
            "val_accuracy": last_metrics["accuracy"],
            "val_macro_recall": last_metrics["macro_recall"],
            "val_loss": last_metrics["loss"],
            "is_best": True,
        }
    elapsed = max(time.perf_counter() - started, 0.001)
    metadata = {
        "model_name": "raptormaps-tiny-thermal-cnn",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image_size": list(DEFAULT_IMAGE_SIZE),
        "classes": list(RAPTORMAPS_CLASSES),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "max_per_class": args.max_per_class,
        "class_weight_power": args.class_weight_power,
        "best_metric": args.best_metric,
        "selected_epoch": best_record["epoch"],
        "selection_policy": f"best validation {args.best_metric}",
        "train_records": len(train_records),
        "val_records": len(val_records),
        "total_train_seconds": round(elapsed, 3),
        "hardware": hardware_metadata(torch, device),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": best_state_dict,
            "classes": list(RAPTORMAPS_CLASSES),
            "image_size": list(DEFAULT_IMAGE_SIZE),
            "metadata": metadata,
            "history": history,
            "final_metrics": best_metrics,
            "last_metrics": last_metrics,
        },
        output_path,
    )

    metrics_path = Path(args.metrics_output)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata,
        "class_distribution": class_distribution(records),
        "train_distribution": class_distribution(train_records),
        "val_distribution": class_distribution(val_records),
        "history": history,
        "final_metrics": best_metrics,
        "last_metrics": last_metrics,
        "artifact_path": str(output_path),
    }
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "event": "saved",
                "artifact": str(output_path),
                "metrics": str(metrics_path),
                "selected_epoch": best_record["epoch"],
                "selected_metric": args.best_metric,
                "selected_score": best_score,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
