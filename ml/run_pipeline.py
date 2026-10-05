"""
AEGIS-SPILL ML Pipeline Orchestrator & CLI
Provides unified commands to inspect data, generate smoke datasets, train, evaluate, and predict.
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.config import config
from ml.create_smoke_dataset import create_smoke_dataset
from ml.data.dataset import inspect_dataset_directory, create_dataloaders
from ml.training.train import train_model
from ml.evaluation.evaluate import evaluate_model
from ml.inference.predict import get_default_predictor


def main():
    parser = argparse.ArgumentParser(description="AEGIS-SPILL ML Pipeline CLI")
    parser.add_argument("--create-smoke-data", action="store_true", help="Generate synthetic multi-scene smoke dataset")
    parser.add_argument("--inspect", type=str, nargs="?", const="default", help="Inspect dataset directory")
    parser.add_argument("--data-dir", type=str, default=None, help="Path to dataset directory")
    parser.add_argument("--train", action="store_true", help="Run model training loop")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation on test split")
    parser.add_argument("--predict", type=str, help="Run inference on satellite image (.npy/.png/.jpg)")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    args = parser.parse_args()

    config.ensure_directories()

    default_dataset = config.DATA_DIR / "zenodo_sentinel1"
    if not default_dataset.exists():
        default_dataset = config.DATA_DIR / "smoke_dataset"
    chosen_data_dir = Path(args.data_dir) if args.data_dir else default_dataset

    if args.create_smoke_data:
        smoke_dir = create_smoke_dataset()
        print(f"Smoke dataset created at: {smoke_dir}")

    if args.inspect:
        target_dir = Path(args.inspect) if args.inspect != "default" else chosen_data_dir
        if not target_dir.exists():
            print(f"Directory {target_dir} does not exist. Creating smoke dataset first...")
            target_dir = create_smoke_dataset()

        summary = inspect_dataset_directory(target_dir)
        # Exclude raw pair objects from pretty print
        summary_clean = {k: v for k, v in summary.items() if k != "pairs"}
        print("\n=== DATASET INSPECTION SUMMARY ===")
        print(json.dumps(summary_clean, indent=2))

    if args.train:
        data_dir = chosen_data_dir
        if not data_dir.exists():
            print(f"[AEGIS-SPILL ML] Dataset not found at {data_dir}. Creating smoke dataset first...")
            data_dir = create_smoke_dataset()

        inspection = inspect_dataset_directory(data_dir)
        pairs = inspection["pairs"]
        print(f"[AEGIS-SPILL ML] Training on dataset: {data_dir.name}")
        print(f"[AEGIS-SPILL ML] Loaded {len(pairs)} image/mask pairs.")

        config.NUM_EPOCHS = args.epochs
        config.BATCH_SIZE = args.batch_size
        config.LEARNING_RATE = args.lr

        dataloaders = create_dataloaders(
            pairs,
            batch_size=config.BATCH_SIZE,
            target_size=config.IMAGE_SIZE,
            seed=config.SEED
        )
        print(f"[AEGIS-SPILL ML] Splits: {dataloaders['splits']}")

        train_summary = train_model(dataloaders["train"], dataloaders["val"], cfg=config)
        print("\n=== TRAINING COMPLETED ===")
        print(f"Best Val Loss: {train_summary['best_metrics'].get('val_loss')}")
        print(f"Best Val IoU: {train_summary['best_metrics'].get('iou')}")
        print(f"Best Val Dice: {train_summary['best_metrics'].get('dice')}")

    if args.evaluate:
        data_dir = chosen_data_dir
        if not data_dir.exists():
            data_dir = create_smoke_dataset()

        inspection = inspect_dataset_directory(data_dir)
        dataloaders = create_dataloaders(
            inspection["pairs"],
            batch_size=config.BATCH_SIZE,
            target_size=config.IMAGE_SIZE,
            seed=config.SEED
        )
        test_metrics = evaluate_model(dataloaders["test"], cfg=config)
        print("\n=== TEST SPLIT EVALUATION METRICS ===")
        print(json.dumps(test_metrics, indent=2))

    if args.predict:
        predictor = get_default_predictor()
        result = predictor.predict(args.predict)
        print("\n=== INFERENCE PREDICTION ===")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
