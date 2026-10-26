"""Load Olist CSVs and map source columns to project contracts.

This stage maps schemas only. Data cleaning decisions, missing-value strategy,
and demand filtering are intentionally deferred to EDA.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

REQUIRED_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
}


class DatasetError(RuntimeError):
    """Raised when raw dataset files or required columns are unavailable."""


def _read_required_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise DatasetError(
            f"Required file not found: {path}. Run python -m scripts.download_olist first."
        )
    frame = pd.read_csv(path, low_memory=False)
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise DatasetError(f"{path.name} is missing required columns: {missing}")
    return frame


def load_olist_raw(raw_dir: Path = RAW_DATA_DIR) -> Dict[str, pd.DataFrame]:
    """Read the core Olist tables required for this prototype."""
    return {
        "orders": _read_required_csv(
            raw_dir / REQUIRED_FILES["orders"],
            {"order_id", "order_purchase_timestamp", "order_status"},
        ),
        "order_items": _read_required_csv(
            raw_dir / REQUIRED_FILES["order_items"],
            {"order_id", "order_item_id", "product_id", "price", "freight_value"},
        ),
        "products": _read_required_csv(
            raw_dir / REQUIRED_FILES["products"],
            {"product_id", "product_category_name", "product_weight_g",
             "product_length_cm", "product_height_cm", "product_width_cm"},
        ),
    }


def normalize_olist(tables: Dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize demand line records and product physical metadata.

    Olist order items do not include an explicit quantity field. Quantity=1 is
    a transparent per-record proxy, not a source-observed unit quantity.
    """
    orders_raw = tables["orders"]
    items_raw = tables["order_items"]
    products_raw = tables["products"]

    order_lookup = orders_raw[
        ["order_id", "order_purchase_timestamp", "order_status"]
    ].copy()
    order_lookup["order_purchase_timestamp"] = pd.to_datetime(
        order_lookup["order_purchase_timestamp"], errors="coerce"
    )
    line_items = items_raw.merge(
        order_lookup, on="order_id", how="left", validate="many_to_one"
    )

    normalized_orders = pd.DataFrame({
        "Order_ID": line_items["order_id"],
        "SKU_ID": line_items["product_id"],
        "Quantity": 1.0,
        "Timestamp": line_items["order_purchase_timestamp"],
        "Order_Status": line_items["order_status"],
        "Order_Item_ID": line_items["order_item_id"],
        "Unit_Price": line_items["price"],
        "Freight_Value": line_items["freight_value"],
    })

    normalized_skus = pd.DataFrame({
        "SKU_ID": products_raw["product_id"],
        "Width_cm": products_raw["product_width_cm"],
        "Height_cm": products_raw["product_height_cm"],
        "Depth_cm": products_raw["product_length_cm"],
        "Weight_kg": products_raw["product_weight_g"] / 1000.0,
        "Category": products_raw["product_category_name"],
        "Hazard_Class": "UNSPECIFIED",
        "Handling_Type": "UNSPECIFIED",
        "Inventory_Units": pd.NA,
    })
    return normalized_orders, normalized_skus
