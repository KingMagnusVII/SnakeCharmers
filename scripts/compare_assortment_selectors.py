"""Bounded, training-only comparison of the three assortment selectors.

This script does not run the warehouse pipeline or evaluate the holdout.  It
uses the existing chronological split, constructs one individually feasible
candidate pool from training demand, and passes that same pool and training
orders to each selector.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

# Allow direct execution with ``python scripts/compare_assortment_selectors.py``.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baseline import select_feasible_candidates, select_order_coverage_candidates
from src.demand_analysis import product_dimensional_fit
from src.inventory_simulation import chronological_train_test_split
from src.milp_assortment import MILPSelectionResult, select_milp_order_coverage_candidates

DEFAULT_POOL_CAP = 500
DEFAULT_MAX_ASSORTMENT = 200
DEFAULT_MAX_TRAINING_ORDERS = 5_000
DEFAULT_MILP_TIMEOUT = 30.0


def sample_training_orders(orders: pd.DataFrame, max_orders: int) -> pd.DataFrame:
    """Keep the earliest complete orders, deterministically, without leakage."""
    valid = orders.loc[orders["Order_ID"].notna()].copy()
    order_index = valid[["Order_ID", "Timestamp"]].drop_duplicates("Order_ID")
    order_index = order_index.sort_values(["Timestamp", "Order_ID"], kind="mergesort", na_position="last")
    selected = set(order_index.head(max(0, int(max_orders)))["Order_ID"])
    return valid.loc[valid["Order_ID"].isin(selected)].copy()


def build_training_candidate_pool(
    profile: pd.DataFrame,
    locations: pd.DataFrame,
    training_orders: pd.DataFrame,
    cap: int,
    allow_rotations: bool,
) -> pd.DataFrame:
    """Build one physical-feasibility-filtered, training-ranked SKU pool."""
    usable = profile.loc[profile["Physical_Metadata_Usable"].fillna(False)].copy()
    fit = product_dimensional_fit(usable, locations, allow_rotations=allow_rotations)
    feasible_ids = set(fit.loc[fit["Fit_Location_Count"] > 0, "SKU_ID"])
    pool = usable.loc[usable["SKU_ID"].isin(feasible_ids)].copy()
    counts = training_orders.groupby("SKU_ID", dropna=True).agg(
        _Training_Order_Lines=("SKU_ID", "size"),
        _Training_Distinct_Orders=("Order_ID", "nunique"),
    )
    pool = pool.join(counts, on="SKU_ID")
    pool["Recorded_Order_Lines"] = pool["_Training_Order_Lines"].fillna(0)
    pool["Distinct_Orders"] = pool["_Training_Distinct_Orders"].fillna(0)
    return pool.sort_values(
        ["Recorded_Order_Lines", "Distinct_Orders", "SKU_ID"],
        ascending=[False, False, True],
        kind="mergesort",
    ).head(max(0, int(cap))).drop(columns=["_Training_Order_Lines", "_Training_Distinct_Orders"])


def calculate_metrics(
    selector: str,
    selected: pd.DataFrame,
    training_orders: pd.DataFrame,
    candidate_pool: pd.DataFrame,
    runtime_seconds: float,
    solver_status: str = "not_applicable",
    optimality_proven: str = "not_applicable",
    max_assortment_size: int = DEFAULT_MAX_ASSORTMENT,
    secondary_changed_selection: str = "not_applicable",
) -> dict:
    """Calculate comparable whole-order coverage metrics."""
    grouped = training_orders.loc[
        training_orders["Order_ID"].notna() & training_orders["SKU_ID"].notna()
    ].groupby("Order_ID", sort=True)["SKU_ID"].agg(lambda values: frozenset(values))
    orders = [items for items in grouped if items]
    pool_ids = set(candidate_pool["SKU_ID"])
    selected_ids = set(selected["SKU_ID"])
    evaluable = [items for items in orders if items <= pool_ids]
    complete = sum(items <= selected_ids for items in orders)
    total = len(orders)
    denominator = len(evaluable)
    size_valid = len(selected_ids) <= int(max_assortment_size)
    return {
        "selector": selector,
        "selected_skus": int(len(selected_ids)),
        "candidate_pool_skus": int(len(pool_ids)),
        "training_orders_evaluated": total,
        "training_orders_evaluable_in_pool": denominator,
        "training_orders_excluded_outside_pool": total - denominator,
        "complete_training_orders": int(complete),
        "candidate_pool_coverage_orders": denominator,
        "candidate_pool_coverage_pct": denominator / total * 100 if total else 0.0,
        "complete_pct_of_evaluable": sum(items <= selected_ids for items in evaluable) / denominator * 100 if denominator else 0.0,
        "complete_pct_of_all_training": complete / total * 100 if total else 0.0,
        "runtime_seconds": float(runtime_seconds),
        "solver_status": solver_status,
        "optimality_proven": optimality_proven,
        "secondary_changed_selection": secondary_changed_selection,
        "selection_size_limit": int(max_assortment_size),
        "selection_size_valid": size_valid,
        "validation_failure": "" if size_valid else f"selected {len(selected_ids)} > limit {max_assortment_size}",
    }


def completed_order_ids(selected: pd.DataFrame, training_orders: pd.DataFrame) -> set:
    """Return IDs of sampled training orders completed by a selected assortment."""
    selected_ids = set(selected["SKU_ID"])
    grouped = training_orders.loc[
        training_orders["Order_ID"].notna() & training_orders["SKU_ID"].notna()
    ].groupby("Order_ID", sort=True)["SKU_ID"].agg(lambda values: frozenset(values))
    return {order_id for order_id, items in grouped.items() if items and items <= selected_ids}


def compare_selector_sets(left: set, right: set, left_name: str = "greedy", right_name: str = "milp") -> dict:
    """Compare two SKU or order ID sets with explicit overlap metrics."""
    union = left | right
    return {
        "left_selector": left_name,
        "right_selector": right_name,
        "shared_count": len(left & right),
        "left_only_count": len(left - right),
        "right_only_count": len(right - left),
        "left_only": sorted(left - right, key=str),
        "right_only": sorted(right - left, key=str),
        "jaccard": len(left & right) / len(union) if union else 1.0,
    }


def compare(args: argparse.Namespace) -> pd.DataFrame:
    """Run the bounded comparison and write CSV plus Markdown summary."""
    processed = ROOT / "data" / "processed"
    config = json.loads((ROOT / "config" / "simulation_config.json").read_text(encoding="utf-8"))
    orders = pd.read_csv(processed / "orders.csv", low_memory=False)
    profile = pd.read_csv(processed / "demand_profile.csv", low_memory=False)
    locations = pd.read_csv(processed / "warehouse_locations.csv", low_memory=False)
    scoped = orders.loc[orders["Order_Status"].isin(config.get("demand_statuses", ["delivered"]))].copy()
    training, _holdout, cutoff = chronological_train_test_split(
        scoped, train_fraction=float(config.get("inventory_simulation", {}).get("train_fraction", 0.8))
    )
    training = sample_training_orders(training, args.max_training_orders)
    pool = build_training_candidate_pool(profile, locations, training, args.candidate_pool_cap, bool(config.get("allow_rotations", True)))
    max_assortment_size = min(max(0, args.max_assortment_size), DEFAULT_MAX_ASSORTMENT)
    selector_config = {**config, "max_active_skus": max_assortment_size, "milp_candidate_pool": 0, "milp_time_limit_seconds": args.milp_timeout}
    rows = []
    selected_by_name = {}
    selected_frames = {}
    for name, function in (("demand_ranked", lambda: select_feasible_candidates(pool, locations, selector_config)), ("greedy_order_coverage", lambda: select_order_coverage_candidates(pool, locations, training, selector_config))):
        started = time.perf_counter()
        selected = function()
        selected_by_name[name] = set(selected["SKU_ID"])
        selected_frames[name] = selected
        rows.append(calculate_metrics(name, selected, training, pool, time.perf_counter() - started, max_assortment_size=max_assortment_size))
    started = time.perf_counter()
    milp_result: MILPSelectionResult = select_milp_order_coverage_candidates(pool, locations, training, selector_config)
    selected_by_name["milp_order_coverage"] = set(milp_result.candidates["SKU_ID"])
    selected_frames["milp_order_coverage"] = milp_result.candidates
    rows.append(calculate_metrics("milp_order_coverage", milp_result.candidates, training, pool, time.perf_counter() - started, str(milp_result.solver_status), str(milp_result.optimality_proven), max_assortment_size, str(milp_result.secondary_changed_selection)))
    metrics = pd.DataFrame(rows)
    differing_pairs = [f"{left}!={right}" for left, left_set in selected_by_name.items() for right, right_set in selected_by_name.items() if left < right and left_set != right_set]
    completed_by_name = {name: completed_order_ids(frame, training) for name, frame in selected_frames.items()}
    sku_comparison = compare_selector_sets(selected_by_name["greedy_order_coverage"], selected_by_name["milp_order_coverage"])
    order_comparison = compare_selector_sets(completed_by_name["greedy_order_coverage"], completed_by_name["milp_order_coverage"], "greedy_order_coverage", "milp_order_coverage")
    sku_rows = [{"selector": name, "SKU_ID": sku} for name, skus in selected_by_name.items() for sku in sorted(skus, key=str)]
    order_rows = [{"Order_ID": order_id, **{f"{name}_complete": order_id in completed for name, completed in completed_by_name.items()}} for order_id in sorted(set().union(*completed_by_name.values()), key=str)]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output_dir / "assortment_selector_comparison.csv", index=False)
    pd.DataFrame(sku_rows, columns=["selector", "SKU_ID"]).to_csv(args.output_dir / "assortment_selector_sku_sets.csv", index=False)
    pd.DataFrame(order_rows).to_csv(args.output_dir / "assortment_selector_order_completions.csv", index=False)
    pd.DataFrame([{key: value for key, value in sku_comparison.items() if key not in {"left_only", "right_only"}}]).to_csv(args.output_dir / "assortment_selector_sku_comparison.csv", index=False)
    pd.DataFrame([{key: value for key, value in order_comparison.items() if key not in {"left_only", "right_only"}}]).to_csv(args.output_dir / "assortment_selector_order_comparison.csv", index=False)
    summary = ["# Assortment selector comparison", "", f"Training split cutoff: `{cutoff}`", f"Training-order sample: earliest {len(training['Order_ID'].unique()):,} complete orders, sorted by timestamp then Order_ID.", f"Candidate pool: {len(pool):,} individually feasible SKUs, ranked by training order lines/distinct orders then SKU_ID; cap={args.candidate_pool_cap}.", f"Maximum assortment size: {selector_config['max_active_skus']:,}; MILP timeout: {args.milp_timeout:g} seconds.", f"Pairwise selected-set differences: {', '.join(differing_pairs) if differing_pairs else 'none; selectors returned identical SKU sets.'}", f"Greedy/MILP SKU Jaccard: {sku_comparison['jaccard']:.6f}; shared={sku_comparison['shared_count']}, greedy-only={sku_comparison['left_only_count']}, MILP-only={sku_comparison['right_only_count']}.", f"Greedy/MILP completed-order overlap: shared={order_comparison['shared_count']}, greedy-only={order_comparison['left_only_count']}, MILP-only={order_comparison['right_only_count']}.", "", metrics.to_markdown(index=False), "", "Primary completion percentages use all sampled complete training orders. Candidate-pool coverage is reported separately.", "Holdout orders were loaded only as the unused split output and were not used for pool construction, selection, tuning, or metrics."]
    (args.output_dir / "assortment_selector_comparison.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-pool-cap", type=int, default=DEFAULT_POOL_CAP)
    parser.add_argument("--max-assortment-size", type=int, default=DEFAULT_MAX_ASSORTMENT)
    parser.add_argument("--max-training-orders", type=int, default=DEFAULT_MAX_TRAINING_ORDERS)
    parser.add_argument("--milp-timeout", type=float, default=DEFAULT_MILP_TIMEOUT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    return parser.parse_args()


if __name__ == "__main__":
    print(compare(parse_args()).to_string(index=False))
