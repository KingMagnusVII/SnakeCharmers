"""Validate existing saved layouts without regenerating allocations or routes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.feasibility import validate_layout


def aggregate_loads(layout: pd.DataFrame, skus: pd.DataFrame, locations: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Report modeled aggregate loads using observed stock or the explicit fallback."""
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


def main() -> None:
    processed, reports = ROOT / "data" / "processed", ROOT / "reports"
    config = json.loads((ROOT / "config" / "simulation_config.json").read_text(encoding="utf-8"))
    skus = pd.read_csv(processed / "sku_master.csv")
    locations = pd.read_csv(processed / "warehouse_locations.csv")
    summary = []
    for name in ("baseline", "optimized"):
        layout = pd.read_csv(processed / f"{name}_allocation.csv")
        validation = validate_layout(layout, skus, locations, config)
        validation.to_csv(reports / f"{name}_layout_validation.csv", index=False)
        validation.loc[validation.Status == "VIOLATION"].to_csv(reports / f"{name}_known_violations.csv", index=False)
        validation.loc[validation.Status == "UNVERIFIED"].to_csv(reports / f"{name}_unverified_safety.csv", index=False)
        validation.loc[validation.Rule.isin(["sku_reference", "location_reference"])].to_csv(reports / f"{name}_unknown_references.csv", index=False)
        aggregate_loads(layout, skus, locations, config).to_csv(reports / f"{name}_aggregate_loads.csv", index=False)
        summary.append({"layout": name, "assignments": len(layout), "known_violations": int((validation.Status == "VIOLATION").sum()), "unverified_checks": int((validation.Status == "UNVERIFIED").sum()), "unknown_references": int(validation.Rule.isin(["sku_reference", "location_reference"]).sum())})
    try:
        unallocated = pd.read_csv(processed / "unallocated_skus.csv")
    except pd.errors.EmptyDataError:
        # Older pipeline runs may have written a zero-byte CSV when no SKUs were excluded.
        unallocated = pd.DataFrame(columns=["SKU_ID", "Reason"])
    unallocated.to_csv(reports / "unallocated_or_infeasible_skus.csv", index=False)
    headers = list(summary[0])
    table = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    table.extend("| " + " | ".join(str(row[column]) for column in headers) + " |" for row in summary)
    report = ["# Correctness hardening report", "", "## Saved-layout validation", "", *table, "", f"Unallocated or infeasible SKUs recorded by the saved baseline: {len(unallocated)}.", "", "## Separate evidence files", "", "Each layout has a structured full validation file plus separate known-violation, unverified-safety, unknown-reference, and aggregate-load CSVs. `unallocated_or_infeasible_skus.csv` preserves the saved baseline exclusions.", "", "## Interpretation", "", "Known violations are only checks with sufficient input data and configured limits. `UNVERIFIED` records indicate missing observed inventory or unknown hazard/handling attributes; they are not safety-compliance results. Aggregate loads use the configured representative inventory fallback where observed inventory is unavailable."]
    (reports / "correctness_hardening_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
