"""Load Olist CSVs and map source columns to project contracts.

This stage maps schemas only. Data cleaning decisions, missing-value strategy,
and demand filtering are intentionally deferred to EDA.
"""
from __future__ import annotations  # Enables modern type annotations.

from pathlib import Path  # Provides cross-platform filesystem paths.
from typing import Dict  # Types the returned table mapping.

import pandas as pd  # Reads and transforms CSV data.

from .operational_data import apply_operational_metadata

# Locate the repository root relative to this source file.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Define the directories containing raw and generated data.
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

# Map logical table names to their Olist source filenames.
REQUIRED_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
}


class DatasetError(RuntimeError):
    """Raised when raw dataset files or required columns are unavailable."""


def _read_required_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    """Read one CSV and verify that every required column exists."""

    # Fail with a useful message instead of a low-level pandas file error.
    if not path.exists():
        raise DatasetError(
            f"Required file not found: {path}. "
            "Run python -m scripts.download_olist first."
        )

    # Load the CSV while disabling low-memory type guessing.
    frame = pd.read_csv(path, low_memory=False)

    # Compare the source schema with the columns required by this project.
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise DatasetError(f"{path.name} is missing required columns: {missing}")

    # Return the validated source table.
    return frame


def load_olist_raw(raw_dir: Path = RAW_DATA_DIR) -> Dict[str, pd.DataFrame]:
    """Read the core Olist tables required for this prototype."""

    # Load orders and require identifiers, timestamp, and status fields.
    orders = _read_required_csv(
        raw_dir / REQUIRED_FILES["orders"],
        {"order_id", "order_purchase_timestamp", "order_status"},
    )

    # Load order-item lines and require pricing and SKU references.
    order_items = _read_required_csv(
        raw_dir / REQUIRED_FILES["order_items"],
        {"order_id", "order_item_id", "product_id", "price", "freight_value"},
    )

    # Load product metadata and require physical dimensions.
    products = _read_required_csv(
        raw_dir / REQUIRED_FILES["products"],
        {
            "product_id",
            "product_category_name",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        },
    )

    # Return the three source tables under stable logical names.
    return {
        "orders": orders,
        "order_items": order_items,
        "products": products,
    }


def normalize_olist(
    tables: Dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize demand lines and product physical metadata."""

    # Extract the raw tables from the logical table mapping.
    orders_raw = tables["orders"]
    items_raw = tables["order_items"]
    products_raw = tables["products"]

    # Keep only order fields needed by the normalized demand contract.
    order_lookup = orders_raw[
        ["order_id", "order_purchase_timestamp", "order_status"]
    ].copy()

    # Convert timestamps to pandas datetime values; invalid values become NaT.
    order_lookup["order_purchase_timestamp"] = pd.to_datetime(
        order_lookup["order_purchase_timestamp"],
        errors="coerce",
    )

    # Attach order timestamp and status to every order-item line.
    line_items = items_raw.merge(
        order_lookup,
        on="order_id",
        how="left",
        validate="many_to_one",
    )

    # Build the normalized demand-line schema.
    normalized_orders = pd.DataFrame(
        {
            "Order_ID": line_items["order_id"],
            "SKU_ID": line_items["product_id"],
            # Olist has no explicit quantity field, so each recorded line is 1.
            "Quantity": 1.0,
            "Timestamp": line_items["order_purchase_timestamp"],
            "Order_Status": line_items["order_status"],
            "Order_Item_ID": line_items["order_item_id"],
            "Unit_Price": line_items["price"],
            "Freight_Value": line_items["freight_value"],
        }
    )

    # Build the normalized SKU physical-metadata schema.
    normalized_skus = pd.DataFrame(
        {
            "SKU_ID": products_raw["product_id"],
            "Width_cm": products_raw["product_width_cm"],
            "Height_cm": products_raw["product_height_cm"],
            # Olist calls length the third product dimension; this project calls it depth.
            "Depth_cm": products_raw["product_length_cm"],
            # Convert Olist grams to the project's kilograms.
            "Weight_kg": products_raw["product_weight_g"] / 1000.0,
            "Category": products_raw["product_category_name"],
            # Olist does not provide verified hazard/handling classifications.
            "Hazard_Class": "UNSPECIFIED",
            "Handling_Type": "UNSPECIFIED",
            # Olist does not provide a current inventory snapshot.
            "Inventory_Units": pd.NA,
        }
    )

    # Apply reviewed operational facts if the optional local overlay exists.
    # The overlay is intentionally not bundled with the repository because its
    # values must come from the actual warehouse and carry provenance.
    normalized_skus, metadata_audit = apply_operational_metadata(normalized_skus)
    normalized_skus.attrs["operational_metadata_audit"] = metadata_audit

    # Return normalized demand lines and SKU metadata separately.
    return normalized_orders, normalized_skus
