"""Download and extract Olist using the Kaggle API client."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATASET_SLUG = "olistbr/brazilian-ecommerce"
EXPECTED_FILES = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_products_dataset.csv",
]


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "kaggle", "datasets", "download",
        "-d", DATASET_SLUG, "-p", str(RAW_DIR), "--unzip",
    ]
    print(f"Downloading Kaggle dataset: {DATASET_SLUG}")
    print("Accept dataset terms and configure Kaggle API credentials before running.")
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print("Kaggle client is unavailable; install requirements.txt first.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            "Download failed. Check Kaggle credentials and dataset access: "
            "https://github.com/Kaggle/kaggle-api#api-credentials",
            file=sys.stderr,
        )
        return exc.returncode or 1

    missing = [name for name in EXPECTED_FILES if not (RAW_DIR / name).exists()]
    if missing:
        print(f"Downloaded archive is missing expected CSV files: {missing}", file=sys.stderr)
        return 1
    print(f"Dataset downloaded and verified in {RAW_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
