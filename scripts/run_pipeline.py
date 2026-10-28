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
from src.demand_analysis import analyze_demand
from src.evaluation import compare, evaluate
from src.feasibility import validate_layout
from src.ml_demand import forecast_next_week_demand
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

    # Also evaluate the first 500 source orders without skipping orders for
    # which the layout contains none of the requested SKUs. This is a separate,
    # broader coverage measure and is not mixed with the historical route sample.
    source_routes = route_orders(
        scoped, optimized, locations, max_orders=500, include_zero_pick_orders=True
    )
    source_order_metrics = evaluate(
        source_routes, optimized, profile, locations, config
    )
    source_routes.to_csv(out / "source_order_routes.csv", index=False)
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
                "Known_Violations": int(baseline_validation["known_violations"]),
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
        "| Strategy | Allocated SKUs | Unallocated selected SKUs | Complete orders | Completion rate | Route distance (m) | Known violations |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in strategy_comparison.to_dict("records"):
        strategy_lines.append(
            f"| {row['Strategy']} | {row['Allocated_SKUs']} | "
            f"{row['Unallocated_selected_SKUs']} | {row['Complete_Orders']} | "
            f"{row['Completion_Rate']:.1%} | {row['Total_Route_Distance_m']:.1f} | "
            f"{row['Known_Violations']} |"
        )
    (reports / "assortment_strategy_comparison.md").write_text(
        "\n".join(strategy_lines) + "\n", encoding="utf-8"
    )

    (reports / "source_order_coverage_report.md").write_text(
        "# Source-order coverage (first 500 source orders)\n\n"
        "This report includes source orders with zero SKUs in the optimized layout. "
        "It is separate from the historical pickable-order route sample, which skips zero-pick orders.\n\n"
        f"- Source orders counted: {source_order_metrics['orders_simulated']}\n"
        f"- Complete orders: {source_order_metrics['complete_orders']}\n"
        f"- Incomplete orders: {source_order_metrics['incomplete_orders']}\n"
        f"- Completion rate: {source_order_metrics['completion_rate']:.1%}\n"
        f"- Orders with zero pickable SKUs: {int((source_routes['Visited_SKUs'].astype(str).str.len() == 0).sum())}\n"
        f"- Route distance: {source_order_metrics['total_distance_m']:.1f} m\n",
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
