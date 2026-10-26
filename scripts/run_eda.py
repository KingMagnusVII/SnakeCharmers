"""Run EDA only; this never invokes allocation, routing, or evaluation stages."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.affinity_analysis import compute_affinity
from src.data_loader import RAW_DATA_DIR
from src.demand_analysis import build_demand_profile, product_dimensional_fit, select_demand_scope

PROCESSED = PROJECT_ROOT / "data" / "processed"
REPORTS = PROJECT_ROOT / "reports"


def _table_audit(path: Path, key: str | None = None) -> dict:
    frame = pd.read_csv(path, low_memory=False)
    return {"file": path.name, "rows": int(len(frame)), "columns": int(len(frame.columns)),
            "key_duplicates": int(frame[key].duplicated().sum()) if key and key in frame else None,
            "missing": {column: int(count) for column, count in frame.isna().sum().items() if count},
            "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()}}


def _write_charts(profile: pd.DataFrame, affinity: pd.DataFrame, fit: pd.DataFrame) -> None:
    positive = profile.loc[profile.Observed_Demand].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(range(1, len(positive) + 1), positive.Cumulative_Demand_Share, label="Cumulative distinct-order contribution")
    ax.set(xlabel="Demand-ranked SKU", ylabel="Cumulative contribution", title="SKU demand Pareto (distinct containing orders)")
    ax.axhline(.80, color="tab:orange", linestyle="--", label="A threshold (80%)"); ax.axhline(.95, color="tab:red", linestyle="--", label="B threshold (95%)")
    ax.legend(); fig.tight_layout(); fig.savefig(REPORTS / "demand_pareto.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 5))
    top = affinity.head(15)
    labels = (top.SKU_A + " – " + top.SKU_B) if not top.empty else []
    ax.barh(list(reversed(labels)), list(reversed(top.Pair_Count)) if not top.empty else [])
    ax.set(xlabel="Distinct orders containing both SKUs", title="Top retained SKU affinity pairs"); fig.tight_layout(); fig.savefig(REPORTS / "affinity_pairs.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5))
    volumes = fit.loc[fit.Dimensions_Valid, "Volume_cm3"].dropna()
    ax.hist(volumes, bins=40); ax.set(xlabel="Product volume (cm³)", ylabel="SKU count", title="Valid product-volume distribution")
    fig.tight_layout(); fig.savefig(REPORTS / "product_volume_distribution.png", dpi=150); plt.close(fig)


def main() -> int:
    config = json.loads((PROJECT_ROOT / "config" / "simulation_config.json").read_text(encoding="utf-8"))
    orders = pd.read_csv(PROCESSED / "orders.csv", low_memory=False)
    skus = pd.read_csv(PROCESSED / "sku_master.csv", low_memory=False)
    locations = pd.read_csv(PROCESSED / "warehouse_locations.csv", low_memory=False)
    print("Loaded normalized inputs", flush=True)
    profile, demand = build_demand_profile(orders, skus, config)
    print("Built demand profile", flush=True)
    scoped = select_demand_scope(orders, config.get("demand_statuses", ["delivered"]))
    min_pair_count = int(config.get("affinity_min_pair_count", 2)); min_support = float(config.get("affinity_min_support", 0.0))
    affinity = compute_affinity(scoped, min_pair_count=min_pair_count, min_support=min_support)
    print("Computed affinity", flush=True)
    fit = product_dimensional_fit(skus, locations, bool(config.get("allow_rotations", True)))
    print("Computed dimensional fit", flush=True)
    PROCESSED.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
    profile.to_csv(PROCESSED / "demand_profile.csv", index=False)
    affinity.to_csv(PROCESSED / "affinity_pairs.csv", index=False)
    fit.to_csv(PROCESSED / "dimensional_fit.csv", index=False)
    raw_specs = {"orders": ("olist_orders_dataset.csv", "order_id"), "order_items": ("olist_order_items_dataset.csv", None), "products": ("olist_products_dataset.csv", "product_id")}
    raw = {name: _table_audit(RAW_DATA_DIR / filename, key) for name, (filename, key) in raw_specs.items()}
    raw_orders = pd.read_csv(RAW_DATA_DIR / raw_specs["orders"][0], usecols=["order_id", "order_purchase_timestamp", "order_status"])
    raw_items = pd.read_csv(RAW_DATA_DIR / raw_specs["order_items"][0], usecols=["order_id", "order_item_id", "product_id"])
    raw_products = pd.read_csv(RAW_DATA_DIR / raw_specs["products"][0], usecols=["product_id"])
    source_quality = {
        "duplicate_order_item_key": int(raw_items.duplicated(["order_id", "order_item_id"]).sum()),
        "items_missing_order_reference": int((~raw_items.order_id.isin(raw_orders.order_id)).sum()),
        "items_missing_product_reference": int((~raw_items.product_id.isin(raw_products.product_id)).sum()),
        "missing_order_identifiers": int(raw_orders.order_id.isna().sum()),
        "missing_item_identifiers": int(raw_items.order_item_id.isna().sum()),
        "missing_product_identifiers": int(raw_items.product_id.isna().sum()),
        "invalid_raw_purchase_timestamps": int(pd.to_datetime(raw_orders.order_purchase_timestamp, errors="coerce").isna().sum()),
        "normalized_line_reconciliation_delta": int(len(orders) - len(raw_items)),
    }
    timestamp_invalid = int(pd.to_datetime(orders.Timestamp, errors="coerce").isna().sum())
    location_dimensions = locations[["Bin_Width_cm", "Bin_Height_cm", "Bin_Depth_cm"]].drop_duplicates().to_dict("records")
    summary = {"raw": raw, "source_quality": source_quality, "demand": demand, "status_distribution": {str(k): int(v) for k, v in orders.Order_Status.value_counts(dropna=False).items()}, "invalid_or_missing_normalized_timestamps": timestamp_invalid, "affinity": {"scope_orders": int(scoped.Order_ID.nunique()), "scope_lines": int(len(scoped)), "min_pair_count": min_pair_count, "min_support": min_support, "retained_pairs": int(len(affinity)), "top_pairs": affinity.head(10).to_dict("records")}, "fit": {"valid_dimension_products": int(fit.Dimensions_Valid.sum()), "metadata_indeterminate": int((~fit.Fit_Determinable).sum()), "no_fit": int(fit.Fits_No_Location.sum()), "small_fit_count_lte_5": int(fit.Small_Fit_Count.sum()), "location_count": int(len(locations)), "location_dimensions_cm": location_dimensions}}
    (REPORTS / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _write_charts(profile, affinity, fit)
    abc = profile.ABC_Class.value_counts().reindex(["A", "B", "C", "ZERO"], fill_value=0).to_dict()
    report = f"""# Exploratory data analysis

## Scope and provenance

This EDA reads local Olist raw tables and normalized `data/processed/orders.csv`, `sku_master.csv`, and `warehouse_locations.csv`. Demand and affinity include only `Order_Status` values configured as {config.get('demand_statuses')}; timestamp quality is reported but timestamps are not an additional exclusion. That yields {demand['scoped_order_lines']:,} recorded lines from {demand['scoped_distinct_orders']:,} orders. Other statuses are excluded. Olist records item lines, not verified shipped-unit quantities; `Recorded_Order_Lines` is retained separately from the primary proxy, distinct orders containing a SKU.

## Quality and reconciliation

    Raw source audit is in `eda_summary.json`: {source_quality['items_missing_order_reference']:,} item lines lack an order reference, {source_quality['items_missing_product_reference']:,} lack a product reference, and the normalized-line reconciliation delta is {source_quality['normalized_line_reconciliation_delta']:,}. The normalized order data has {timestamp_invalid:,} missing/unparseable timestamps. The demand universe has {demand['positive_demand_skus']:,} observed-demand SKUs, {demand['zero_demand_skus']:,} zero-demand product-master SKUs, and {demand['unmatched_observed_skus']:,} observed SKUs absent from the product master. Product placement cannot be assessed for {demand['products_missing_or_invalid_dimensions']:,} products with missing/invalid dimensions and {demand['products_missing_or_invalid_weight']:,} with missing/invalid weight.

## Demand and ABC/Pareto

The denominator is {demand['sku_order_incidence_denominator']:,} SKU-order incidences (the sum of per-SKU distinct-order counts), not distinct orders. Rows are ranked by distinct-order count then SKU ID. ABC uses cumulative share after each SKU: A through 80%, B through 95%, C thereafter; zero-demand rows are explicitly `ZERO` and do not affect that denominator. Counts: {abc}. Distinct-order frequency is a pick-frequency proxy, not inventory or unit sales.

## Affinity

Baskets deduplicate repeated SKUs within an order. Retained observed pairs require count ≥ {min_pair_count} and support ≥ {min_support}; {len(affinity):,} pairs remain. Support, both confidence directions, and lift use the same {demand['scoped_distinct_orders']:,}-order scope. Affinity is historical co-occurrence, not causation or proof that adjacency improves future picks.

## Dimensional fit

Warehouse locations use {location_dimensions}; units are centimetres, matching Olist product dimensions. The synthetic location universe has {len(locations):,} locations. Of {int(fit.Dimensions_Valid.sum()):,} validly measured products, {int(fit.Fits_No_Location.sum()):,} fit no location under configured rotations={bool(config.get('allow_rotations', True))}; {int(fit.Small_Fit_Count.sum()):,} fit 1–5 locations (a descriptive, not safety, threshold). All current locations share effective bin dimensions, limiting differentiated slotting. No actual warehouse inventory/occupancy is inferred.

## Artifacts and limitations

Generated: `data/processed/demand_profile.csv`, `affinity_pairs.csv`, `dimensional_fit.csv`; charts `demand_pareto.png`, `affinity_pairs.png`, and `product_volume_distribution.png`; audit `eda_summary.json`. Warehouse geometry is synthetic, and Olist lacks inventory, hazard, handling, and verified quantities. This entry point does not run baseline allocation, optimization, routes, or evaluation.
"""
    (REPORTS / "eda_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
