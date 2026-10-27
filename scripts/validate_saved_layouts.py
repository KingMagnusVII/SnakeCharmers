"""Validate saved layouts and optionally fail when operational SKU data is incomplete."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.feasibility import validate_layout


def aggregate_loads(layout: pd.DataFrame, skus: pd.DataFrame, locations: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Report modeled aggregate loads using observed stock or simulation fallback."""
    joined = layout[["SKU_ID", "Location_ID"]].merge(skus[["SKU_ID", "Weight_kg", "Inventory_Units"]], on="SKU_ID", how="left").merge(locations[["Location_ID", "Rack_ID", "Bay", "Shelf_Level", "Shelf_Max_Load_kg", "Rack_Max_Load_kg"]], on="Location_ID", how="left")
    units = pd.to_numeric(joined["Inventory_Units"], errors="coerce").fillna(config["representative_inventory_units"])
    joined["Modeled_Load_kg"] = pd.to_numeric(joined["Weight_kg"], errors="coerce") * units
    shelf = joined.groupby(["Rack_ID", "Bay", "Shelf_Level", "Shelf_Max_Load_kg"], dropna=False).agg(Modeled_Load_kg=("Modeled_Load_kg", "sum"), Assigned_SKUs=("SKU_ID", "count")).reset_index()
    shelf["Scope"] = "shelf"
    shelf["Limit_kg"] = shelf.pop("Shelf_Max_Load_kg")
    rack = joined.groupby(["Rack_ID", "Rack_Max_Load_kg"], dropna=False).agg(Modeled_Load_kg=("Modeled_Load_kg", "sum"), Assigned_SKUs=("SKU_ID", "count")).reset_index()
    rack["Scope"] = "rack"
    rack["Limit_kg"] = rack.pop("Rack_Max_Load_kg")
    return pd.concat([shelf, rack], ignore_index=True, sort=False)


def _missing_text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(True, index=frame.index)
    return frame[column].isna() | frame[column].astype(str).str.strip().str.upper().isin(
        ["", "UNKNOWN", "UNSPECIFIED", "N/A", "NA", "NONE"]
    )


def operational_metadata_gaps(assigned_skus: pd.DataFrame) -> dict[str, int]:
    """Count missing inventory, safety classifications, and evidence provenance."""
    inventory = pd.to_numeric(
        assigned_skus.get("Inventory_Units", pd.Series(index=assigned_skus.index, dtype=float)),
        errors="coerce",
    )
    return {
        "missing_inventory_skus": int((inventory.isna() | (inventory < 0)).sum()),
        "missing_hazard_class_skus": int(_missing_text(assigned_skus, "Hazard_Class").sum()),
        "missing_handling_type_skus": int(_missing_text(assigned_skus, "Handling_Type").sum()),
        "missing_inventory_provenance_skus": int(
            (_missing_text(assigned_skus, "Inventory_Snapshot_At") |
             _missing_text(assigned_skus, "Inventory_Data_Source")).sum()
        ),
        "missing_safety_provenance_skus": int(
            (_missing_text(assigned_skus, "Safety_Verified_By") |
             _missing_text(assigned_skus, "Safety_Verified_At") |
             _missing_text(assigned_skus, "Safety_Data_Source")).sum()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-operational-data",
        action="store_true",
        help="exit with code 2 if allocated SKUs lack non-negative inventory, reviewed safety classifications, or provenance",
    )
    args = parser.parse_args()

    processed, reports = ROOT / "data" / "processed", ROOT / "reports"
    config = json.loads((ROOT / "config" / "simulation_config.json").read_text(encoding="utf-8"))
    skus = pd.read_csv(processed / "sku_master.csv")
    locations = pd.read_csv(processed / "warehouse_locations.csv")
    summary = []
    all_metadata_complete = True
    for name in ("baseline", "optimized"):
        layout = pd.read_csv(processed / f"{name}_allocation.csv")
        validation = validate_layout(layout, skus, locations, config)
        validation.to_csv(reports / f"{name}_layout_validation.csv", index=False)
        validation.loc[validation.Status == "VIOLATION"].to_csv(reports / f"{name}_known_violations.csv", index=False)
        validation.loc[validation.Status == "UNVERIFIED"].to_csv(reports / f"{name}_unverified_safety.csv", index=False)
        validation.loc[validation.Rule.isin(["sku_reference", "location_reference"])].to_csv(reports / f"{name}_unknown_references.csv", index=False)
        aggregate_loads(layout, skus, locations, config).to_csv(reports / f"{name}_aggregate_loads.csv", index=False)

        assigned = layout[["SKU_ID"]].drop_duplicates().merge(skus, on="SKU_ID", how="left")
        gaps = operational_metadata_gaps(assigned)
        metadata_complete = all(value == 0 for value in gaps.values())
        all_metadata_complete = all_metadata_complete and metadata_complete
        summary.append({
            "layout": name,
            "assignments": len(layout),
            "known_violations": int((validation.Status == "VIOLATION").sum()),
            "unverified_checks": int((validation.Status == "UNVERIFIED").sum()),
            "unknown_references": int(validation.Rule.isin(["sku_reference", "location_reference"]).sum()),
            **gaps,
            "operational_metadata_complete": metadata_complete,
        })

    try:
        unallocated = pd.read_csv(processed / "unallocated_skus.csv")
    except pd.errors.EmptyDataError:
        unallocated = pd.DataFrame(columns=["SKU_ID", "Reason"])
    unallocated.to_csv(reports / "unallocated_or_infeasible_skus.csv", index=False)
    headers = list(summary[0])
    table = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    table.extend("| " + " | ".join(str(row[column]) for column in headers) + " |" for row in summary)
    report = [
        "# Correctness hardening report", "",
        "## Saved-layout validation", "", *table, "",
        f"Unallocated or infeasible SKUs recorded by the saved baseline: {len(unallocated)}.", "",
        "## Separate evidence files", "",
        "Each layout has a structured full validation file plus separate known-violation, unverified-safety, unknown-reference, and aggregate-load CSVs. The unallocated_or_infeasible_skus.csv file preserves the saved baseline exclusions.", "",
        "## Interpretation", "",
        "Known violations are checks with enough input data to demonstrate a configured rule was broken. UNVERIFIED means evidence is missing; it is not a compliance result. Aggregate loads use the configured representative-stock fallback when observed inventory is absent, so those load figures are simulation estimates.", "",
        "Operational metadata completeness checks positive inventory counts, non-placeholder hazard/handling classifications, and recorded provenance. Passing this check does not certify a facility: actual rack ratings, geometry, compatibility rules, and local safety requirements still require verification.", "",
        f"Strict operational-data gate requested: {args.strict_operational_data}.",
    ]
    (reports / "correctness_hardening_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(pd.DataFrame(summary).to_string(index=False))
    if args.strict_operational_data and not all_metadata_complete:
        print(
            "\nSTRICT CHECK FAILED: one or more allocated SKUs lack verified inventory, "
            "hazard/handling classifications, or provenance. This layout is not ready "
            "for operational use. Populate data/input/sku_operational_metadata.csv and rerun.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if args.strict_operational_data:
        print("\nOperational SKU metadata completeness gate passed. This is not a site-safety certification.")


if __name__ == "__main__":
    main()
