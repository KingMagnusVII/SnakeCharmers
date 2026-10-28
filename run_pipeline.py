"""Run the complete reproducible prototype pipeline."""

from __future__ import annotations  # Enables modern type annotations.

import json  # Reads the simulation configuration and writes JSON reports.
import sys  # Lets the script import the project package when run directly.
import time  # Measures end-to-end pipeline runtime.
from pathlib import Path  # Provides cross-platform filesystem paths.

# Resolve the repository root from this script's location.
ROOT = Path(__file__).resolve().parent

# Make the repository root importable when this file is executed directly.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import each stage of the warehouse-slotting pipeline.
from src.affinity_analysis import compute_affinity
from src.baseline import allocate_baseline, select_feasible_candidates
from src.data_loader import load_olist_raw, normalize_olist
from src.demand_analysis import analyze_demand
from src.evaluation import compare, evaluate
from src.feasibility import validate_layout
from src.optimizer import improve_layout_by_route_distance, optimize_layout
from src.routing import route_orders
from src.warehouse_generator import generate_warehouse


def optimize_and_refine_layout(profile, locations, baseline, affinity, scoped, config):
    """Run greedy optimization followed by bounded route-distance refinement."""

    greedy, opt_info = optimize_layout(
        profile,
        locations,
        baseline,
        affinity,
        config,
    )
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

    candidates = {
        "baseline": baseline,
        "greedy": greedy,
        "refined": refined,
    }
    candidate_metrics = {}
    feasible_candidates = {}
    for name, candidate in candidates.items():
        validation = validate_layout(candidate, profile, locations, config)
        violations = int((validation["Status"] == "VIOLATION").sum()) if not validation.empty else 0
        route_table = route_orders(scoped, candidate, locations, max_orders=500)
        distance = float(route_table["Distance_m"].sum()) if not route_table.empty else 0.0
        candidate_metrics[name] = {
            "total_route_distance_m": distance,
            "known_violations": violations,
        }
        if violations == 0:
            feasible_candidates[name] = distance

    selected_name = min(
        feasible_candidates,
        key=lambda name: (feasible_candidates[name], ("baseline", "greedy", "refined").index(name)),
    )
    optimized = candidates[selected_name]
    opt_info["local_search"] = local_search_info
    opt_info["candidate_layouts"] = candidate_metrics
    opt_info["selected_layout"] = selected_name
    opt_info["selection_reason"] = (
        f"{selected_name} has the lowest total simulated route distance among feasible candidates"
    )
    return optimized, opt_info


def main() -> None:
    """Run every pipeline stage and save its outputs and reports."""

    # Start a high-resolution timer so runtime can be included in the final report.
    start = time.perf_counter()

    # Define output directories and create them if they do not already exist.
    out = ROOT / "data" / "processed"
    reports = ROOT / "reports"
    out.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    # Load the simulation settings from the JSON configuration file.
    config = json.loads(
        (ROOT / "config" / "simulation_config.json").read_text(encoding="utf-8")
    )

    # Load the raw Olist tables from data/raw.
    tables = load_olist_raw(ROOT / "data" / "raw")

    # Convert raw Olist schemas into the project's normalized order and SKU tables.
    orders, skus = normalize_olist(tables)

    # Generate the deterministic synthetic warehouse topology.
    locations = generate_warehouse()

    # Persist the normalized inputs so later stages can inspect/reuse them.
    orders.to_csv(out / "orders.csv", index=False)
    skus.to_csv(out / "sku_master.csv", index=False)
    locations.to_csv(out / "warehouse_locations.csv", index=False)

    # Build the demand profile and collect data-quality information.
    profile, quality = analyze_demand(orders, skus, config)
    profile.to_csv(out / "demand_profile.csv", index=False)

    # Restrict historical demand to the order statuses configured for the simulation.
    scoped = orders[orders.Order_Status.isin(config["demand_statuses"])]

    # Select demand-ranked SKUs that fit at least one location before capping.
    active = set(select_feasible_candidates(profile, locations, config).SKU_ID)

    # Calculate SKU-pair co-occurrence for the active assortment.
    affinity = compute_affinity(scoped, active)

    # Create the deterministic baseline allocation and record excluded SKUs.
    baseline, excluded = allocate_baseline(profile, locations, config)

    # Improve the baseline using the project's feasible greedy heuristic,
    # followed by bounded route-distance local search.
    optimized, opt_info = optimize_and_refine_layout(
        profile,
        locations,
        baseline,
        affinity,
        scoped,
        config,
    )

    # Persist both layouts and the SKUs that were not allocated.
    baseline.to_csv(out / "baseline_allocation.csv", index=False)
    optimized.to_csv(out / "optimized_allocation.csv", index=False)
    excluded.to_csv(out / "unallocated_skus.csv", index=False)

    # Independently validate both layouts against physical and safety constraints.
    baseline_violations = validate_layout(
        baseline,
        skus,
        locations,
        config["allow_rotations"],
    )
    optimized_violations = validate_layout(
        optimized,
        skus,
        locations,
        config["allow_rotations"],
    )

    # Save validation findings for downstream reports/dashboard use.
    baseline_violations.to_csv(out / "baseline_violations.csv", index=False)
    optimized_violations.to_csv(out / "optimized_violations.csv", index=False)

    # Generate pick routes for both layouts using the same demand scope.
    baseline_routes = route_orders(scoped, baseline, locations)
    optimized_routes = route_orders(scoped, optimized, locations)
    baseline_routes.to_csv(out / "baseline_routes.csv", index=False)
    optimized_routes.to_csv(out / "optimized_routes.csv", index=False)

    # Calculate metrics for both layouts and compare them.
    baseline_metrics = evaluate(
        baseline_routes,
        baseline,
        profile,
        locations,
        config,
    )
    optimized_metrics = evaluate(
        optimized_routes,
        optimized,
        profile,
        locations,
        config,
    )
    comparison = compare(baseline_metrics, optimized_metrics)
    comparison.to_csv(out / "evaluation_comparison.csv", index=False)

    # Write a short audit report describing the data foundation.
    (reports / "data_foundation_audit.md").write_text(
        "# Data foundation audit\n\n"
        "Verified raw tables, normalized schemas, 240 generated locations, "
        "and deterministic inputs.\n\n"
        "```json\n"
        + json.dumps(quality, indent=2, default=str)
        + "\n```\n",
        encoding="utf-8",
    )

    # Write the EDA summary report using the same quality metadata.
    (reports / "eda_report.md").write_text(
        "# EDA report\n\n"
        "Demand scope: delivered orders. Quantity is a recorded order-line "
        "proxy, not actual units.\n\n"
        + json.dumps(quality, indent=2, default=str)
        + "\n",
        encoding="utf-8",
    )

    # Record the optimizer's heuristic metadata and its limitations.
    (reports / "optimization_report.md").write_text(
        "# Optimization report\n\n"
        "Heuristic feasible reassignment; no global optimality claim.\n\n"
        + json.dumps(opt_info, indent=2)
        + "\n",
        encoding="utf-8",
    )

    # Save the final comparison table and measured runtime.
    runtime_seconds = round(time.perf_counter() - start, 2)
    (reports / "final_validation_report.md").write_text(
        "# Final validation report\n\n"
        "```text\n"
        + comparison.to_string(index=False)
        + "\n```\n\n"
        + f"Runtime seconds: {runtime_seconds}\n",
        encoding="utf-8",
    )

    # Print a machine-readable summary for terminals and automation.
    print(
        json.dumps(
            {
                "baseline": baseline_metrics,
                "optimized": optimized_metrics,
                "baseline_violations": len(baseline_violations),
                "optimized_violations": len(optimized_violations),
                "runtime_seconds": runtime_seconds,
            },
            indent=2,
        )
    )


# Run the pipeline when this file is executed as a script/module entry point.
if __name__ == "__main__":
    main()
