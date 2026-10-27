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
from src.baseline import allocate_baseline
from src.data_loader import load_olist_raw, normalize_olist
from src.demand_analysis import analyze_demand
from src.evaluation import compare, evaluate
from src.feasibility import validate_layout
from src.ml_demand import forecast_next_week_demand
from src.optimizer import improve_layout_by_route_distance, optimize_layout
from src.routing import route_orders, select_fully_allocatable_orders
from src.warehouse_generator import generate_warehouse


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
    metadata_audit = skus.attrs.get("operational_metadata_audit", {"overlay_found": False})
    locations = generate_warehouse()

    orders.to_csv(out / "orders.csv", index=False)
    skus.to_csv(out / "sku_master.csv", index=False)
    locations.to_csv(out / "warehouse_locations.csv", index=False)

    profile, quality = analyze_demand(orders, skus, config)

    # Stage 10: learn temporal demand patterns and forecast the next week.
    profile, ml_info = forecast_next_week_demand(orders, profile, config)
    profile.to_csv(out / "demand_profile.csv", index=False)
    profile.to_csv(out / "ml_demand_forecast.csv", index=False)

    scoped = orders[orders.Order_Status.isin(config["demand_statuses"])]

    # Keep end-to-end source coverage separate from route efficiency among
    # orders whose every SKU is represented in the active assortment.
    source_order_sample = scoped

    # Build the historical baseline first. This keeps the benchmark independent
    # of ML so the final evaluation can show whether ML actually improves it.
    baseline, excluded = allocate_baseline(profile, locations, config)

    eligible_orders_all = select_fully_allocatable_orders(
        scoped, baseline, max_orders=None
    )
    eligible_order_ids = (
        eligible_orders_all["Order_ID"].drop_duplicates().head(500).tolist()
    )
    route_sample_orders = eligible_orders_all[
        eligible_orders_all["Order_ID"].isin(eligible_order_ids)
    ].copy()
    if route_sample_orders.empty:
        raise RuntimeError(
            "No fully allocatable orders exist for the route-efficiency cohort. "
            "Inspect the active assortment and source data before evaluating routes."
        )

    # Diagnose every active SKU that could not be allocated. This makes it clear
    # whether the bottleneck is physical dimensions or remaining constraints.
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
        reason_summary["SKU_Count"] / len(excluded)
        if len(excluded)
        else 0.0
    )
    reason_summary.to_csv(out / "unallocated_reason_summary.csv", index=False)

    # Use the exact baseline assortment for affinity analysis so both strategies
    # are compared on the same SKUs. The optimizer then uses ML demand priority
    # when deciding which of those SKUs gets the best feasible locations.
    active = set(baseline.SKU_ID)
    affinity = compute_affinity(scoped, active)
    affinity.to_csv(out / "affinity_pairs.csv", index=False)

    # Stage 11: optimize the same assortment with ML priority + affinity while
    # retaining hard feasibility and distance/ergonomic objectives.
    greedy, opt_info = optimize_layout(
        profile, locations, baseline, affinity, config
    )
    refined, local_search_info = improve_layout_by_route_distance(
        profile,
        locations,
        greedy,
        route_sample_orders,
        config,
        max_swap_attempts=config.get("max_local_search_iterations", 100),
        max_passes=1,
        max_orders=500,
    )

    # Compare candidates on the same route sample and keep only layouts with no
    # known hard-constraint violations. This prevents refinement from making a
    # route improvement at the expense of warehouse feasibility.
    candidates = {"baseline": baseline, "greedy": greedy, "refined": refined}
    candidate_metrics = {}
    feasible_candidates = {}
    for name, candidate in candidates.items():
        validation = validate_layout(candidate, skus, locations, config)
        violations = (
            int((validation["Status"] == "VIOLATION").sum())
            if not validation.empty
            else 0
        )
        candidate_routes = route_orders(route_sample_orders, candidate, locations, max_orders=500)
        distance = (
            float(candidate_routes["Distance_m"].sum())
            if not candidate_routes.empty
            else 0.0
        )
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
    tie_break_order = {"baseline": 0, "greedy": 1, "refined": 2}
    selected_name = min(
        feasible_candidates,
        key=lambda name: (feasible_candidates[name], tie_break_order[name]),
    )
    optimized = candidates[selected_name]
    opt_info["local_search"] = local_search_info
    opt_info["candidate_layouts"] = candidate_metrics
    opt_info["selected_layout"] = selected_name
    opt_info["selection_reason"] = (
        f"{selected_name} has the lowest simulated route distance among layouts "
        "with no known hard-constraint violations"
    )

    baseline.to_csv(out / "baseline_allocation.csv", index=False)
    optimized.to_csv(out / "optimized_allocation.csv", index=False)

    baseline_violations = validate_layout(
        baseline, skus, locations, config["allow_rotations"]
    )
    optimized_violations = validate_layout(
        optimized, skus, locations, config["allow_rotations"]
    )
    baseline_violations.to_csv(out / "baseline_violations.csv", index=False)
    optimized_violations.to_csv(out / "optimized_violations.csv", index=False)
    baseline_validation = _validation_summary(baseline_violations)
    optimized_validation = _validation_summary(optimized_violations)

    baseline_routes = route_orders(route_sample_orders, baseline, locations)
    optimized_routes = route_orders(route_sample_orders, optimized, locations)
    source_sample_baseline_routes = route_orders(source_order_sample, baseline, locations, max_orders=500)
    source_sample_optimized_routes = route_orders(source_order_sample, optimized, locations, max_orders=500)
    source_sample_metrics = {
        "baseline": evaluate(source_sample_baseline_routes, baseline, profile, locations, config),
        "optimized": evaluate(source_sample_optimized_routes, optimized, profile, locations, config),
    }

    baseline_routes.to_csv(out / "baseline_routes.csv", index=False)
    optimized_routes.to_csv(out / "optimized_routes.csv", index=False)

    baseline_metrics = evaluate(
        baseline_routes, baseline, profile, locations, config
    )
    optimized_metrics = evaluate(
        optimized_routes, optimized, profile, locations, config
    )
    comparison = compare(baseline_metrics, optimized_metrics)
    comparison.to_csv(out / "evaluation_comparison.csv", index=False)

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

    # Explain why active-assortment SKUs remain unallocated so the next
    # optimization step can target the real bottleneck instead of guessing.
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
        "Route-distance comparison uses up to 500 orders whose every SKU is allocated. This conditional route-efficiency cohort is not overall source-order coverage; the first 500 source orders are reported separately in the console.\n\n"
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
                "evaluation_scope": {
                    "eligible_orders_available": int(eligible_orders_all["Order_ID"].nunique()),
                    "eligible_orders_evaluated": int(route_sample_orders["Order_ID"].nunique()),
                    "eligible_order_completion_rate": baseline_metrics["completion_rate"],
                    "source_sample_definition": "first 500 source orders, including orders with no allocated SKUs",
                },
                "source_first_500_orders": source_sample_metrics,
                "baseline": baseline_metrics,
                "optimized": optimized_metrics,
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
