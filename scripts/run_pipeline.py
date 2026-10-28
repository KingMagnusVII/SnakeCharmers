"""Run the complete reproducible prototype pipeline."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.affinity_analysis import compute_affinity
from src.baseline import allocate_baseline, select_feasible_candidates, select_order_coverage_candidates
from src.data_loader import load_olist_raw, normalize_olist
import pandas as pd

from src.demand_analysis import analyze_demand, product_dimensional_fit
from src.evaluation import compare, evaluate
from src.feasibility import validate_layout
from src.ml_demand import forecast_next_week_demand
from src.inventory_simulation import (
    chronological_train_test_split,
    estimate_starting_inventory,
    simulate_inventory_picking,
)
from src.optimizer import improve_layout_by_route_distance, optimize_layout
from src.routing import route_orders
from src.warehouse_generator import generate_warehouse


def optimize_and_refine_layout(profile, locations, baseline, affinity, scoped, config):
    """Run greedy optimization followed by bounded route-distance refinement."""
    greedy, opt_info = optimize_layout(profile, locations, baseline, affinity, config)
    refined, local_search_info = improve_layout_by_route_distance(
        profile,
        locations,
        greedy,
        scoped,
        config,
        max_swap_attempts=config["max_local_search_iterations"],
        max_passes=1,
        max_orders=500,
    )

    candidates = {"baseline": baseline, "greedy": greedy, "refined": refined}
    candidate_metrics = {}
    feasible_candidates = {}
    for name, candidate in candidates.items():
        validation = validate_layout(candidate, profile, locations, config)
        violations = int((validation["Status"] == "VIOLATION").sum()) if not validation.empty else 0
        route_table = route_orders(scoped, candidate, locations, max_orders=500, include_zero_pick_orders=False)
        distance = float(route_table["Distance_m"].sum()) if not route_table.empty else 0.0
        candidate_metrics[name] = {
            "total_route_distance_m": distance,
            "known_violations": violations,
        }
        if violations == 0:
            feasible_candidates[name] = distance

    if not feasible_candidates:
        raise RuntimeError(
            "No baseline, greedy, or refined layout passed hard-constraint validation."
        )

    selected_name = min(
        feasible_candidates,
        key=lambda name: (
            feasible_candidates[name],
            ("baseline", "greedy", "refined").index(name),
        ),
    )
    optimized = candidates[selected_name]
    opt_info["local_search"] = local_search_info
    opt_info["candidate_layouts"] = candidate_metrics
    opt_info["selected_layout"] = selected_name
    opt_info["selection_reason"] = (
        f"{selected_name} has the lowest total simulated route distance among feasible candidates"
    )
    return optimized, opt_info


def _validation_summary(results):
    """Separate confirmed violations from checks that remain unverified."""
    if "Status" not in results.columns:
        return {"known_violations": 0, "unverified_checks": 0}
    return {
        "known_violations": int((results["Status"] == "VIOLATION").sum()),
        "unverified_checks": int((results["Status"] == "UNVERIFIED").sum()),
    }


def _source_order_sample(orders, max_orders=500):
    """Select the earliest distinct source orders by timestamp, deterministically."""
    valid = orders.loc[orders["Order_ID"].notna()].copy()
    order_index = valid[["Order_ID"] + (["Timestamp"] if "Timestamp" in valid else [])].drop_duplicates("Order_ID")
    if "Timestamp" in order_index:
        order_index["Timestamp"] = pd.to_datetime(order_index["Timestamp"], errors="coerce")
        order_index = order_index.sort_values(
            ["Timestamp", "Order_ID"], kind="mergesort", na_position="last"
        )
    else:
        order_index = order_index.sort_values("Order_ID", kind="mergesort")
    selected_ids = set(order_index.head(max(0, int(max_orders)))["Order_ID"])
    return valid.loc[valid["Order_ID"].isin(selected_ids)].copy()


def _source_sku_diagnosis(source_orders, profile, locations, candidates, layout, config, routes):
    """Explain why source-order SKUs are not present in a feasible allocated layout."""
    dimensional_fit = product_dimensional_fit(
        profile,
        locations,
        allow_rotations=bool(config.get("allow_rotations", True)),
    ).set_index("SKU_ID")
    profile_by_sku = profile.drop_duplicates("SKU_ID").set_index("SKU_ID")
    candidate_ids = set(candidates["SKU_ID"]) if "SKU_ID" in candidates else set()
    allocated_ids = set(layout["SKU_ID"]) if "SKU_ID" in layout else set()
    zero_order_ids = set(
        routes.loc[routes["Visited_SKUs"].fillna("").astype(str).eq(""), "Order_ID"]
    )
    rows = []
    sku_orders = source_orders.loc[
        source_orders["Order_ID"].notna() & source_orders["SKU_ID"].notna(),
        ["Order_ID", "SKU_ID"],
    ].drop_duplicates()
    source_line_counts = source_orders.groupby("SKU_ID").size().to_dict()
    for sku, group in sku_orders.groupby("SKU_ID", sort=True):
        if sku in allocated_ids:
            reason = "allocated_and_pickable"
        elif sku not in profile_by_sku.index or not bool(
            profile_by_sku.loc[sku].get("Physical_Metadata_Usable", False)
        ):
            reason = "missing_or_invalid_physical_metadata"
        elif sku in dimensional_fit.index and int(
            dimensional_fit.loc[sku, "Fit_Location_Count"]
        ) == 0:
            reason = "does_not_fit_any_location"
        elif sku in candidate_ids:
            reason = "selected_but_not_allocated"
        else:
            reason = "feasible_but_excluded_by_assortment_cap"
        zero_affected = int(group.loc[group["Order_ID"].isin(zero_order_ids), "Order_ID"].nunique())
        rows.append({
            "SKU_ID": sku,
            "Diagnosis": reason,
            "Source_Order_Count": int(group["Order_ID"].nunique()),
            "Source_Order_Line_Count": int(source_line_counts.get(sku, 0)),
            "Zero_Pick_Orders_Affected": zero_affected,
        })
    detail = pd.DataFrame(rows, columns=[
        "SKU_ID", "Diagnosis", "Source_Order_Count",
        "Source_Order_Line_Count", "Zero_Pick_Orders_Affected",
    ])
    summary = (
        detail.groupby("Diagnosis", as_index=False)
        .agg(
            Distinct_SKUs=("SKU_ID", "nunique"),
            Source_Order_Lines=("Source_Order_Line_Count", "sum"),
            Distinct_Source_Orders=("Source_Order_Count", "sum"),
            Zero_Pick_Order_SKU_Incidences=("Zero_Pick_Orders_Affected", "sum"),
        )
        .sort_values("Diagnosis", kind="mergesort")
        if not detail.empty else pd.DataFrame(columns=[
            "Diagnosis", "Distinct_SKUs", "Source_Order_Lines",
            "Distinct_Source_Orders", "Zero_Pick_Order_SKU_Incidences",
        ])
    )
    return detail, summary


def _run_inventory_holdout_experiment(orders, skus, locations, config, out, reports):
    """Estimate 14-day simulated stock from earlier orders; replay later orders only."""
    settings = config.get("inventory_simulation", {})
    coverage_days = int(settings.get("coverage_days", 14))
    train_fraction = float(settings.get("train_fraction", 0.8))
    max_test_orders = int(settings.get("max_test_orders", 0))
    scoped = orders.loc[orders["Order_Status"].isin(config["demand_statuses"])].copy()
    train_orders, later_orders, cutoff = chronological_train_test_split(scoped, train_fraction=train_fraction)
    train_profile, training_quality = analyze_demand(train_orders, skus, config)
    train_profile = train_profile.loc[train_profile["Recorded_Order_Lines"] > 0].copy()
    train_profile, ml_info = forecast_next_week_demand(train_orders, train_profile, config)
    inventory_estimates, training_days = estimate_starting_inventory(train_orders, coverage_days=coverage_days)
    stock_by_sku = inventory_estimates.set_index("SKU_ID")["Starting_Inventory_Units"].to_dict()
    train_profile["Inventory_Units"] = train_profile["SKU_ID"].map(stock_by_sku).fillna(0).astype(int)
    candidates = select_feasible_candidates(train_profile, locations, config)
    baseline, excluded = allocate_baseline(train_profile, locations, config, candidates=candidates)
    training_skus = set(baseline["SKU_ID"])
    inventory_estimates = inventory_estimates.loc[inventory_estimates["SKU_ID"].isin(training_skus)].copy()
    training_affinity = compute_affinity(train_orders, training_skus)
    optimized, opt_info = optimize_and_refine_layout(train_profile, locations, baseline, training_affinity, train_orders, config)
    if set(baseline["SKU_ID"]) != set(optimized["SKU_ID"]):
        raise RuntimeError("Fair holdout comparison requires baseline and optimized layouts to contain the same SKU assortment.")
    test_orders = later_orders
    if max_test_orders > 0:
        order_index = test_orders[["Order_ID", "Timestamp"]].drop_duplicates("Order_ID").sort_values(["Timestamp", "Order_ID"], kind="mergesort")
        keep_ids = set(order_index.head(max_test_orders)["Order_ID"])
        test_orders = test_orders.loc[test_orders["Order_ID"].isin(keep_ids)].copy()
    baseline_routes, baseline_ledger, baseline_metrics = simulate_inventory_picking(test_orders, baseline, locations, inventory_estimates)
    optimized_routes, optimized_ledger, optimized_metrics = simulate_inventory_picking(test_orders, optimized, locations, inventory_estimates)
    baseline_routes.to_csv(out / "inventory_holdout_baseline_routes.csv", index=False)
    optimized_routes.to_csv(out / "inventory_holdout_optimized_routes.csv", index=False)
    baseline_ledger.to_csv(out / "inventory_holdout_baseline_stock_ledger.csv", index=False)
    optimized_ledger.to_csv(out / "inventory_holdout_optimized_stock_ledger.csv", index=False)
    inventory_estimates.to_csv(out / "inventory_holdout_starting_inventory.csv", index=False)
    baseline.to_csv(out / "inventory_holdout_baseline_layout.csv", index=False)
    optimized.to_csv(out / "inventory_holdout_optimized_layout.csv", index=False)
    excluded.to_csv(out / "inventory_holdout_unallocated_skus.csv", index=False)
    comparison_rows = []
    for metric in sorted(set(baseline_metrics) | set(optimized_metrics)):
        base_value, opt_value = baseline_metrics.get(metric), optimized_metrics.get(metric)
        comparison_rows.append({"Metric": metric, "Baseline": base_value, "Optimized": opt_value, "Change_Optimized_Minus_Baseline": opt_value - base_value if isinstance(base_value, (int, float)) and isinstance(opt_value, (int, float)) else None})
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(out / "inventory_holdout_comparison.csv", index=False)
    split_info = {
        "training_order_count": int(train_orders["Order_ID"].nunique()),
        "test_order_count_before_limit": int(later_orders["Order_ID"].nunique()),
        "test_order_count_evaluated": int(test_orders["Order_ID"].nunique()),
        "training_start": str(train_orders["Timestamp"].min()), "training_end": str(train_orders["Timestamp"].max()),
        "test_start": str(later_orders["Timestamp"].min()), "test_end": str(later_orders["Timestamp"].max()),
        "cutoff_timestamp_exclusive_for_training": str(cutoff), "training_days": int(training_days),
        "coverage_days": int(coverage_days), "max_test_orders_config": int(max_test_orders),
        "starting_inventory_is_simulated": True,
        "inventory_source": "ceil(training-period recorded order-item lines per day × coverage days)",
        "training_demand_quality": training_quality, "training_forecast": ml_info,
        "training_optimization": opt_info, "baseline": baseline_metrics, "optimized": optimized_metrics,
    }
    (reports / "inventory_holdout_experiment.json").write_text(json.dumps(split_info, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        "# Chronological inventory and picking holdout experiment", "", "## Data boundary", "",
        f"- Training orders: {split_info['training_order_count']:,}, from {split_info['training_start']} through {split_info['training_end']}.",
        f"- Test orders evaluated: {split_info['test_order_count_evaluated']:,}, from {split_info['test_start']} through {split_info['test_end']}.",
        f"- Timestamp cutoff: {cutoff}; training timestamps are strictly earlier.",
        f"- Starting-stock rule: {coverage_days} days, estimated only from training order-item lines over {training_days} calendar days.", "",
        "## Important interpretation", "",
        "These quantities are **simulated starting inventory**, not actual Kaggle inventory. Olist provides historical order-item lines, not on-hand stock. Each line is treated as one demand unit because the source has no explicit quantity field. Starting stock is ceil(daily recorded-line demand × coverage days). Stock is decremented only when an entire order can be fulfilled; failed orders do not consume inventory. Unallocated SKUs are reported separately from stockouts.", "",
        "The baseline and optimized layouts use the same training-derived SKU assortment, same starting inventory, and same later test orders. Route optimization/refinement uses training orders only; later test orders are held out for evaluation.", "",
        "## Test metrics", "",
        "| Metric | Baseline | Optimized | Change (optimized − baseline) |", "|---|---:|---:|---:|",
    ]
    for row in comparison.to_dict("records"):
        lines.append(f"| {row['Metric']} | {row['Baseline']} | {row['Optimized']} | {row['Change_Optimized_Minus_Baseline']} |")
    lines.extend(["", "## Reproducible metric payload", "", "```text", comparison.to_string(index=False), "```", ""])
    (reports / "inventory_holdout_experiment.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"inventory_holdout_experiment": {"training_orders": split_info["training_order_count"], "test_orders": split_info["test_order_count_evaluated"], "coverage_days": coverage_days, "baseline": baseline_metrics, "optimized": optimized_metrics, "report": "reports/inventory_holdout_experiment.md"}}, indent=2, default=str))

def main() -> None:
    """Run every stage of the warehouse-slotting pipeline."""
    start = time.perf_counter()
    out = ROOT / "data" / "processed"
    reports = ROOT / "reports"
    out.mkdir(exist_ok=True)
    reports.mkdir(exist_ok=True)

    config = json.loads(
        (ROOT / "config" / "simulation_config.json").read_text(encoding="utf-8")
    )
    tables = load_olist_raw(ROOT / "data" / "raw")
    orders, skus = normalize_olist(tables)
    metadata_audit = skus.attrs.get(
        "operational_metadata_audit", {"overlay_found": False}
    )
    locations = generate_warehouse()

    orders.to_csv(out / "orders.csv", index=False)
    skus.to_csv(out / "sku_master.csv", index=False)
    locations.to_csv(out / "warehouse_locations.csv", index=False)

    profile, quality = analyze_demand(orders, skus, config)
    profile, ml_info = forecast_next_week_demand(orders, profile, config)
    profile.to_csv(out / "demand_profile.csv", index=False)
    profile.to_csv(out / "ml_demand_forecast.csv", index=False)

    scoped = orders[orders.Order_Status.isin(config["demand_statuses"])]

    baseline, excluded = allocate_baseline(profile, locations, config)

    excluded.to_csv(out / "unallocated_skus.csv", index=False)
    reason_summary = (
        excluded["Reason"]
        .value_counts()
        .rename_axis("Reason")
        .reset_index(name="SKU_Count")
        if not excluded.empty
        else __import__("pandas").DataFrame(columns=["Reason", "SKU_Count"])
    )
    reason_summary["Share_of_Unallocated"] = (
        reason_summary["SKU_Count"] / len(excluded) if len(excluded) else 0.0
    )
    reason_summary.to_csv(out / "unallocated_reason_summary.csv", index=False)

    active = set(baseline.SKU_ID)
    affinity = compute_affinity(scoped, active)
    affinity.to_csv(out / "affinity_pairs.csv", index=False)

    optimized, opt_info = optimize_and_refine_layout(
        profile,
        locations,
        baseline,
        affinity,
        scoped,
        config,
    )

    baseline.to_csv(out / "baseline_allocation.csv", index=False)
    optimized.to_csv(out / "optimized_allocation.csv", index=False)

    baseline_violations = validate_layout(baseline, skus, locations, config)
    optimized_violations = validate_layout(optimized, skus, locations, config)
    baseline_violations.to_csv(out / "baseline_violations.csv", index=False)
    optimized_violations.to_csv(out / "optimized_violations.csv", index=False)
    baseline_validation = _validation_summary(baseline_violations)
    optimized_validation = _validation_summary(optimized_violations)

    baseline_routes = route_orders(scoped, baseline, locations, include_zero_pick_orders=False)
    optimized_routes = route_orders(scoped, optimized, locations, include_zero_pick_orders=False)
    baseline_routes.to_csv(out / "baseline_routes.csv", index=False)
    optimized_routes.to_csv(out / "optimized_routes.csv", index=False)

    baseline_metrics = evaluate(baseline_routes, baseline, profile, locations, config)
    optimized_metrics = evaluate(optimized_routes, optimized, profile, locations, config)
    comparison = compare(baseline_metrics, optimized_metrics)
    comparison.to_csv(out / "evaluation_comparison.csv", index=False)

    # Compare the current demand-ranked assortment with an order-coverage-first
    # assortment under the same dimensional, rack-load, and layout constraints.
    demand_ranked_candidates = select_feasible_candidates(profile, locations, config)
    coverage_candidates = select_order_coverage_candidates(
        profile, locations, scoped, config
    )
    coverage_baseline, coverage_excluded = allocate_baseline(
        profile, locations, config, candidates=coverage_candidates
    )
    coverage_affinity = compute_affinity(scoped, set(coverage_baseline.SKU_ID))
    coverage_optimized, coverage_opt_info = optimize_and_refine_layout(
        profile,
        locations,
        coverage_baseline,
        coverage_affinity,
        scoped,
        config,
    )
    coverage_routes = route_orders(scoped, coverage_optimized, locations, include_zero_pick_orders=False)
    coverage_metrics = evaluate(
        coverage_routes, coverage_optimized, profile, locations, config
    )

    # Evaluate the earliest 500 distinct delivered source orders, including
    # orders for which the layout contains none of the requested SKUs.
    source_sample = _source_order_sample(scoped, max_orders=500)
    source_routes = route_orders(
        source_sample, optimized, locations, max_orders=500, include_zero_pick_orders=True
    )
    source_order_metrics = evaluate(
        source_routes, optimized, profile, locations, config
    )
    coverage_source_routes = route_orders(
        source_sample, coverage_optimized, locations,
        max_orders=500, include_zero_pick_orders=True,
    )
    coverage_source_metrics = evaluate(
        coverage_source_routes, coverage_optimized, profile, locations, config
    )
    source_routes.to_csv(out / "source_order_routes.csv", index=False)
    coverage_source_routes.to_csv(
        out / "source_order_routes_coverage_first.csv", index=False
    )

    source_diagnosis_detail, source_diagnosis_summary = _source_sku_diagnosis(
        source_sample, profile, locations, demand_ranked_candidates,
        optimized, config, source_routes,
    )
    source_diagnosis_detail.to_csv(
        out / "source_order_sku_diagnosis.csv", index=False
    )
    source_diagnosis_summary.to_csv(
        out / "source_order_sku_diagnosis_summary.csv", index=False
    )
    strategy_comparison = __import__("pandas").DataFrame(
        [
            {
                "Strategy": "Demand-ranked (current)",
                "Allocated_SKUs": int(baseline.SKU_ID.nunique()),
                "Unallocated_selected_SKUs": max(
                    int(len(demand_ranked_candidates)) - int(baseline.SKU_ID.nunique()), 0
                ),
                "Complete_Orders": int(optimized_metrics["complete_orders"]),
                "Completion_Rate": float(optimized_metrics["completion_rate"]),
                "Total_Route_Distance_m": float(optimized_metrics["total_distance_m"]),
                "Known_Violations": int(optimized_validation["known_violations"]),
                "Source_Complete_Orders": int(source_order_metrics["complete_orders"]),
                "Source_Completion_Rate": float(source_order_metrics["completion_rate"]),
                "Source_Zero_Pick_Orders": int(
                    source_routes["Visited_SKUs"].fillna("").astype(str).eq("").sum()
                ),
                "Source_Route_Distance_m": float(source_order_metrics["total_distance_m"]),
            },
            {
                "Strategy": "Order-coverage-first",
                "Allocated_SKUs": int(coverage_optimized.SKU_ID.nunique()),
                "Unallocated_selected_SKUs": max(
                    int(len(coverage_candidates)) - int(coverage_optimized.SKU_ID.nunique()), 0
                ),
                "Complete_Orders": int(coverage_metrics["complete_orders"]),
                "Completion_Rate": float(coverage_metrics["completion_rate"]),
                "Total_Route_Distance_m": float(coverage_metrics["total_distance_m"]),
                "Known_Violations": int(
                    _validation_summary(
                        validate_layout(
                            coverage_optimized, skus, locations, config
                        )
                    )["known_violations"]
                ),
                "Source_Complete_Orders": int(coverage_source_metrics["complete_orders"]),
                "Source_Completion_Rate": float(coverage_source_metrics["completion_rate"]),
                "Source_Zero_Pick_Orders": int(
                    coverage_source_routes["Visited_SKUs"].fillna("").astype(str).eq("").sum()
                ),
                "Source_Route_Distance_m": float(coverage_source_metrics["total_distance_m"]),
            },
        ]
    )
    strategy_comparison.to_csv(
        out / "assortment_strategy_comparison.csv", index=False
    )
    strategy_lines = [
        "# Assortment strategy comparison",
        "",
        "Both strategies use the same SKU cap, physical-fit checks, hard constraints, "
        "historical 500-order pickable sample, and route-distance refinement. "
        "Route distance and completion metrics are taken from each strategy's optimized layout.",
        "",
        "| Strategy | Allocated SKUs | Unallocated selected SKUs | Pickable-sample complete | Pickable-sample rate | Pickable route distance (m) | Source complete (500) | Source rate | Source zero-pick orders | Source route distance (m) | Known violations |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in strategy_comparison.to_dict("records"):
        strategy_lines.append(
            f"| {row['Strategy']} | {row['Allocated_SKUs']} | "
            f"{row['Unallocated_selected_SKUs']} | {row['Complete_Orders']} | "
            f"{row['Completion_Rate']:.1%} | {row['Total_Route_Distance_m']:.1f} | "
            f"{row['Source_Complete_Orders']} | {row['Source_Completion_Rate']:.1%} | "
            f"{row['Source_Zero_Pick_Orders']} | {row['Source_Route_Distance_m']:.1f} | "
            f"{row['Known_Violations']} |"
        )
    (reports / "assortment_strategy_comparison.md").write_text(
        "\n".join(strategy_lines) + "\n", encoding="utf-8"
    )

    (reports / "source_order_coverage_report.md").write_text(
        "# Source-order coverage (earliest 500 delivered orders)\n\n"
        "The sample is selected by purchase timestamp, not lexicographic order ID. "
        "Both assortment strategies are evaluated on the same source-order sample. "
        "This is separate from the historical pickable-order route sample.\n\n"
        "| Strategy | Source orders | Complete | Incomplete | Completion rate | Zero-pick orders | Route distance (m) |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
        f"| Demand-ranked | {source_order_metrics['orders_simulated']} | "
        f"{source_order_metrics['complete_orders']} | {source_order_metrics['incomplete_orders']} | "
        f"{source_order_metrics['completion_rate']:.1%} | "
        f"{int(source_routes['Visited_SKUs'].fillna('').astype(str).eq('').sum())} | "
        f"{source_order_metrics['total_distance_m']:.1f} |\n"
        f"| Order-coverage-first | {coverage_source_metrics['orders_simulated']} | "
        f"{coverage_source_metrics['complete_orders']} | {coverage_source_metrics['incomplete_orders']} | "
        f"{coverage_source_metrics['completion_rate']:.1%} | "
        f"{int(coverage_source_routes['Visited_SKUs'].fillna('').astype(str).eq('').sum())} | "
        f"{coverage_source_metrics['total_distance_m']:.1f} |\n\n"
        "## Why source-order SKUs are not pickable\n\n"
        "Counts below are SKU incidences in the source sample. "
        "Zero-pick order incidences can overlap because one order may contain multiple SKU causes.\n\n"
        "| Diagnosis | Distinct SKUs | Source order lines | Distinct source orders (summed per SKU) | Zero-pick order incidences |\n"
        "|---|---:|---:|---:|---:|\n"
        + "".join(
            f"| {row['Diagnosis']} | {int(row['Distinct_SKUs'])} | "
            f"{int(row['Source_Order_Lines'])} | {int(row['Distinct_Source_Orders'])} | "
            f"{int(row['Zero_Pick_Order_SKU_Incidences'])} |\n"
            for row in source_diagnosis_summary.to_dict("records")
        )
        + "\nDiagnosis definitions:\n\n"
        "- missing_or_invalid_physical_metadata: product lacks usable dimensions or positive weight.\n"
        "- does_not_fit_any_location: physical metadata is usable, but no generated bin dimensions fit.\n"
        "- feasible_but_excluded_by_assortment_cap: SKU could fit but was not selected by the demand-ranked assortment.\n"
        "- selected_but_not_allocated: SKU was selected but not assigned a feasible slot.\n"
        "- allocated_and_pickable: SKU is present in the layout.\n",
        encoding="utf-8",
    )

    (reports / "data_foundation_audit.md").write_text(
        "# Data foundation audit\n\n"
        "Verified raw tables, normalized schemas, "
        f"{len(locations)} generated warehouse locations, and deterministic inputs.\n\n"
        "Operational metadata overlay audit:\n\n"
        "```json\n"
        + json.dumps(metadata_audit, indent=2, default=str)
        + "\n```\n\n"
        "```json\n"
        + json.dumps(quality, indent=2, default=str)
        + "\n```\n",
        encoding="utf-8",
    )

    (reports / "eda_report.md").write_text(
        "# EDA report\n\n"
        "Demand scope: delivered orders. Quantity is a recorded order-line "
        "proxy, not actual units.\n\n"
        + json.dumps(quality, indent=2, default=str)
        + "\n",
        encoding="utf-8",
    )

    (reports / "ml_demand_report.md").write_text(
        "# ML demand forecasting report\n\n"
        "The model predicts next-week SKU demand from temporal lag/rolling "
        "features, historical demand, and product category.\n\n"
        + json.dumps(ml_info, indent=2, default=str)
        + "\n\n"
        "The forecast is used by the optimized allocator as a priority signal: "
        "higher predicted-demand SKUs are considered first for the best feasible "
        "locations. The historical baseline remains unchanged for comparison.\n",
        encoding="utf-8",
    )

    (reports / "optimization_report.md").write_text(
        "# Optimization report\n\n"
        "Heuristic feasible reassignment using ML demand priority, warehouse "
        "distance, ergonomics, and order affinity; no global optimality claim.\n\n"
        + json.dumps(opt_info, indent=2)
        + "\n",
        encoding="utf-8",
    )

    reason_lines = [
        "# Unallocated SKU diagnosis",
        "",
        f"Active assortment: {len(baseline) + len(excluded)} SKUs.",
        f"Allocated: {len(baseline)} SKUs.",
        f"Unallocated: {len(excluded)} SKUs.",
        "",
        "| Reason | SKU count | Share of unallocated |",
        "|---|---:|---:|",
    ]
    if reason_summary.empty:
        reason_lines.append("| None | 0 | 0.0% |")
    else:
        for _, row in reason_summary.iterrows():
            reason_lines.append(
                f"| {row['Reason']} | {int(row['SKU_Count'])} | "
                f"{row['Share_of_Unallocated']:.1%} |"
            )
    reason_lines.extend(
        [
            "",
            "Interpretation:",
            "- `does_not_fit_any_bin_dimensions` means the SKU cannot physically fit in any generated bin, even with allowed rotation.",
            "- `no_remaining_feasible_location` means at least one bin is dimensionally suitable, but all such locations were unavailable or violated another hard constraint when the SKU was considered.",
        ]
    )
    (reports / "unallocated_sku_diagnosis.md").write_text(
        "\n".join(reason_lines) + "\n",
        encoding="utf-8",
    )

    runtime_seconds = round(time.perf_counter() - start, 2)
    (reports / "final_validation_report.md").write_text(
        "# Final validation report\n\n"
        "Confirmed constraint violations and unverified checks are counted separately. "
        "UNVERIFIED means source data is missing or unknown; it is not evidence of compliance.\n\n"
        "| Layout | Confirmed violations | Unverified checks |\n"
        "|---|---:|---:|\n"
        f"| Baseline | {baseline_validation['known_violations']} | {baseline_validation['unverified_checks']} |\n"
        f"| Optimized | {optimized_validation['known_violations']} | {optimized_validation['unverified_checks']} |\n\n"
        "Evaluation metrics:\n\n"
        "```text\n"
        + comparison.to_string(index=False)
        + "\n```\n\n"
        + f"Runtime seconds: {runtime_seconds}\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "baseline": baseline_metrics,
                "optimized": optimized_metrics,
                "source_order_coverage_first_500": source_order_metrics,
                "source_orders_with_zero_pickable_skus": int(
                    (source_routes["Visited_SKUs"].astype(str).str.len() == 0).sum()
                ),
                "baseline_violations": baseline_validation["known_violations"],
                "baseline_unverified_checks": baseline_validation["unverified_checks"],
                "optimized_violations": optimized_validation["known_violations"],
                "optimized_unverified_checks": optimized_validation["unverified_checks"],
                "unallocated_reason_counts": reason_summary.set_index("Reason")["SKU_Count"].to_dict(),
                "ml_demand": ml_info,
                "optimization": opt_info,
                "runtime_seconds": runtime_seconds,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
