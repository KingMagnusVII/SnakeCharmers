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
from src.optimizer import optimize_layout
from src.routing import route_orders
from src.warehouse_generator import generate_warehouse


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

    # Build the historical baseline first. This keeps the benchmark independent
    # of ML so the final evaluation can show whether ML actually improves it.
    baseline, excluded = allocate_baseline(profile, locations, config)

    # Use the exact baseline assortment for affinity analysis so both strategies
    # are compared on the same SKUs. The optimizer then uses ML demand priority
    # when deciding which of those SKUs gets the best feasible locations.
    active = set(baseline.SKU_ID)
    affinity = compute_affinity(scoped, active)
    affinity.to_csv(out / "affinity_pairs.csv", index=False)

    # Stage 11: optimize the same assortment with ML priority + affinity while
    # retaining hard feasibility and distance/ergonomic objectives.
    optimized, opt_info = optimize_layout(
        profile, locations, baseline, affinity, config
    )

    baseline.to_csv(out / "baseline_allocation.csv", index=False)
    optimized.to_csv(out / "optimized_allocation.csv", index=False)
    excluded.to_csv(out / "unallocated_skus.csv", index=False)

    baseline_violations = validate_layout(
        baseline, skus, locations, config["allow_rotations"]
    )
    optimized_violations = validate_layout(
        optimized, skus, locations, config["allow_rotations"]
    )
    baseline_violations.to_csv(out / "baseline_violations.csv", index=False)
    optimized_violations.to_csv(out / "optimized_violations.csv", index=False)

    baseline_routes = route_orders(scoped, baseline, locations)
    optimized_routes = route_orders(scoped, optimized, locations)
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
        "Verified raw tables, normalized schemas, 240 generated locations, "
        "and deterministic inputs.\n\n"
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

    runtime_seconds = round(time.perf_counter() - start, 2)
    (reports / "final_validation_report.md").write_text(
        "# Final validation report\n\n"
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
                "baseline_violations": len(baseline_violations),
                "optimized_violations": len(optimized_violations),
                "ml_demand": ml_info,
                "optimization": opt_info,
                "runtime_seconds": runtime_seconds,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
