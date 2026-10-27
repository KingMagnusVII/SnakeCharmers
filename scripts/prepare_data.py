"""Create normalized Olist files and generated warehouse topology."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import PROCESSED_DATA_DIR, RAW_DATA_DIR, load_olist_raw, normalize_olist
from src.warehouse_generator import generate_warehouse


def main() -> int:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        tables = load_olist_raw(RAW_DATA_DIR)
    except Exception as exc:
        print(f"Could not load Olist data: {exc}", file=sys.stderr)
        print("Run python -m scripts.download_olist and retry.", file=sys.stderr)
        return 1

    orders, skus = normalize_olist(tables)
    metadata_audit = skus.attrs.get("operational_metadata_audit", {"overlay_found": False})
    locations = generate_warehouse()
    outputs = {
        "orders.csv": orders,
        "sku_master.csv": skus,
        "warehouse_locations.csv": locations,
    }
    for filename, frame in outputs.items():
        path = PROCESSED_DATA_DIR / filename
        frame.to_csv(path, index=False)
        print(f"{filename}: {len(frame):,} rows -> {path.relative_to(PROJECT_ROOT)}")

    print("\nOperational metadata overlay: " + str(metadata_audit))
    print("Assumptions: Quantity=1 is a per-order-item proxy. Missing inventory uses simulation fallback only.")
    print("Hazard/handling attributes remain unverified unless supplied with provenance. Topology and distances are synthetic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
