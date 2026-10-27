"""Load reviewed operational SKU metadata that is absent from Olist.

The overlay is optional for simulation runs. Supplied values are validated and
must include provenance so an operator can audit inventory and safety claims.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA_PATH = PROJECT_ROOT / "data" / "input" / "sku_operational_metadata.csv"
REQUIRED_COLUMNS = [
    "SKU_ID",
    "Inventory_Units",
    "Hazard_Class",
    "Handling_Type",
    "Inventory_Snapshot_At",
    "Inventory_Data_Source",
    "Safety_Verified_By",
    "Safety_Verified_At",
    "Safety_Data_Source",
]


class OperationalMetadataError(ValueError):
    """Raised when operational metadata is ambiguous, invalid, or unauditable."""


def apply_operational_metadata(
    skus: pd.DataFrame,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> tuple[pd.DataFrame, dict]:
    """Apply a validated SKU override file and return the merged master plus audit.

    Blank overlay cells do not overwrite existing values. Inventory is a current
    on-hand unit count; historical order lines are never used as inventory.
    """
    result = skus.copy()
    for column in REQUIRED_COLUMNS[1:]:
        if column not in result.columns:
            result[column] = pd.NA

    if not metadata_path.exists():
        return result, {
            "overlay_found": False,
            "overlay_path": str(metadata_path),
            "overlay_rows": 0,
            "inventory_values_applied": 0,
            "safety_records_applied": 0,
        }

    overlay = pd.read_csv(metadata_path, dtype={"SKU_ID": "string"}, keep_default_na=True)
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(overlay.columns))
    if missing_columns:
        raise OperationalMetadataError(
            f"{metadata_path} is missing required columns: {missing_columns}"
        )

    overlay = overlay[REQUIRED_COLUMNS].copy()
    overlay["SKU_ID"] = overlay["SKU_ID"].astype("string").str.strip()
    overlay = overlay.loc[overlay["SKU_ID"].notna() & overlay["SKU_ID"].ne("")].copy()
    if overlay["SKU_ID"].duplicated().any():
        duplicates = sorted(overlay.loc[overlay["SKU_ID"].duplicated(False), "SKU_ID"].astype(str).unique())
        raise OperationalMetadataError(f"Duplicate SKU_ID values in operational metadata: {duplicates}")

    known_skus = set(result["SKU_ID"].dropna().astype(str))
    unknown_skus = sorted(set(overlay["SKU_ID"].astype(str)) - known_skus)
    if unknown_skus:
        raise OperationalMetadataError(
            f"Operational metadata references SKU_ID values absent from the product master: {unknown_skus[:20]}"
        )

    for column in ("Inventory_Units",):
        supplied = overlay[column].notna()
        numeric = pd.to_numeric(overlay.loc[supplied, column], errors="coerce")
        invalid = numeric.isna() | (numeric <= 0) | (numeric % 1 != 0)
        if invalid.any():
            bad_rows = overlay.loc[supplied].loc[invalid, "SKU_ID"].astype(str).tolist()
            raise OperationalMetadataError(
                f"{column} must be a positive whole-number on-hand quantity; invalid SKUs: {bad_rows[:20]}"
            )

    def nonblank(frame: pd.DataFrame, column: str) -> pd.Series:
        return frame[column].fillna("").astype(str).str.strip().ne("")

    inventory_supplied = overlay["Inventory_Units"].notna()
    inventory_provenance_ok = nonblank(overlay, "Inventory_Snapshot_At") & nonblank(overlay, "Inventory_Data_Source")
    if (inventory_supplied & ~inventory_provenance_ok).any():
        bad = overlay.loc[inventory_supplied & ~inventory_provenance_ok, "SKU_ID"].astype(str).tolist()
        raise OperationalMetadataError(
            "Inventory_Units requires Inventory_Snapshot_At and Inventory_Data_Source; "
            f"missing provenance for SKUs: {bad[:20]}"
        )
    if inventory_supplied.any():
        dates = pd.to_datetime(overlay.loc[inventory_supplied, "Inventory_Snapshot_At"], errors="coerce", utc=True)
        if dates.isna().any():
            bad = overlay.loc[inventory_supplied].loc[dates.isna(), "SKU_ID"].astype(str).tolist()
            raise OperationalMetadataError(f"Invalid Inventory_Snapshot_At for SKUs: {bad[:20]}")

    safety_fields_supplied = nonblank(overlay, "Hazard_Class") | nonblank(overlay, "Handling_Type")
    safety_provenance_ok = (
        nonblank(overlay, "Safety_Verified_By")
        & nonblank(overlay, "Safety_Verified_At")
        & nonblank(overlay, "Safety_Data_Source")
    )
    if (safety_fields_supplied & ~safety_provenance_ok).any():
        bad = overlay.loc[safety_fields_supplied & ~safety_provenance_ok, "SKU_ID"].astype(str).tolist()
        raise OperationalMetadataError(
            "Hazard_Class/Handling_Type require Safety_Verified_By, Safety_Verified_At, "
            f"and Safety_Data_Source; missing provenance for SKUs: {bad[:20]}"
        )
    if safety_fields_supplied.any():
        dates = pd.to_datetime(overlay.loc[safety_fields_supplied, "Safety_Verified_At"], errors="coerce", utc=True)
        if dates.isna().any():
            bad = overlay.loc[safety_fields_supplied].loc[dates.isna(), "SKU_ID"].astype(str).tolist()
            raise OperationalMetadataError(f"Invalid Safety_Verified_At for SKUs: {bad[:20]}")

    forbidden_unknowns = {"", "UNKNOWN", "UNSPECIFIED", "N/A", "NA"}
    for column in ("Hazard_Class", "Handling_Type"):
        supplied = nonblank(overlay, column)
        unknown = overlay[column].fillna("").astype(str).str.strip().str.upper().isin(forbidden_unknowns)
        if (supplied & unknown).any():
            bad = overlay.loc[supplied & unknown, "SKU_ID"].astype(str).tolist()
            raise OperationalMetadataError(
                f"{column} must contain a reviewed classification, not a placeholder; SKUs: {bad[:20]}"
            )

    indexed = overlay.set_index("SKU_ID")
    result_ids = result["SKU_ID"].astype("string")
    for column in REQUIRED_COLUMNS[1:]:
        values = result_ids.map(indexed[column])
        supplied = values.notna()
        if column in ("Hazard_Class", "Handling_Type", "Inventory_Data_Source",
                      "Inventory_Snapshot_At", "Safety_Verified_By",
                      "Safety_Verified_At", "Safety_Data_Source"):
            supplied &= values.astype("string").str.strip().ne("")
        result.loc[supplied, column] = values.loc[supplied].to_numpy()

    return result, {
        "overlay_found": True,
        "overlay_path": str(metadata_path),
        "overlay_rows": int(len(overlay)),
        "inventory_values_applied": int(inventory_supplied.sum()),
        "safety_records_applied": int(safety_fields_supplied.sum()),
    }
