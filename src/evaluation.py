"""Metrics calculated from generated layouts and route records."""
from __future__ import annotations  # Enables modern type annotations.

from numbers import Real  # Lets comparison identify numeric metric values.

import pandas as pd  # Provides DataFrame operations.


def _completion_mask(routes: pd.DataFrame) -> pd.Series:
    """Return true for completed routes, including CSV-loaded string flags."""

    # Empty route tables cannot contain completed orders.
    if routes.empty or "Complete" not in routes:
        return pd.Series(False, index=routes.index)

    # Accept both Python booleans and strings loaded back from CSV.
    return routes["Complete"].map(
        lambda value: value is True or str(value).strip().lower() == "true"
    )


def _complete_orders(routes: pd.DataFrame) -> int:
    """Count true completion flags consistently for bool or CSV string inputs."""

    return int(_completion_mask(routes).sum())


def evaluate(routes, layout, profile, locations, config):
    """Calculate route, utilization, coverage, and data-quality metrics."""

    # Count simulated routes/orders.
    route_count = len(routes)
    completion_mask = _completion_mask(routes)

    complete_orders = int(completion_mask.sum())
    incomplete_orders = route_count - complete_orders

    # Total distance across all simulated routes.
    distance = float(routes["Distance_m"].sum()) if route_count else 0.0

    # Separate completed and incomplete route distances.
    complete_distance = (
        float(routes.loc[completion_mask, "Distance_m"].sum())
        if complete_orders
        else 0.0
    )

    incomplete_distance = (
        float(routes.loc[~completion_mask, "Distance_m"].sum())
        if incomplete_orders
        else 0.0
    )

    # Keep only warehouse locations used by the supplied layout.
    selected = locations[locations.Location_ID.isin(layout.Location_ID)]

    # Keep only profile rows represented in the layout.
    profile_rows = profile[profile.SKU_ID.isin(layout.SKU_ID)]

    # Calculate total physical capacity across the warehouse.
    capacity = float(locations.Volumetric_Capacity_cm3.sum())

    # Estimate occupied volume from the modeled representative stock.
    used = float(profile_rows.Volume_cm3.fillna(0).sum())

    # Calculate capacity of only the bins selected by the layout.
    selected_capacity = float(selected.Volumetric_Capacity_cm3.sum())

    # Count recorded demand lines represented by the whole profile.
    order_lines = float(profile.Recorded_Order_Lines.sum())

    # Return all metrics in one dictionary for report generation.
    return {
        "orders_simulated": int(route_count),
        "complete_orders": complete_orders,
        "incomplete_orders": incomplete_orders,
        "completion_rate": complete_orders / route_count if route_count else 0.0,
        "total_distance_m": distance,
        "completed_route_distance_m": complete_distance,
        "incomplete_route_distance_m": incomplete_distance,
        "average_distance_incomplete_orders_m": (
            incomplete_distance / incomplete_orders
            if incomplete_orders
            else 0.0
        ),
        "average_distance_m": distance / route_count if route_count else 0.0,
        # No completed orders uses 0.0 because a completed-order average is undefined.
        "average_distance_complete_orders_m": (
            complete_distance / complete_orders if complete_orders else 0.0
        ),
        "estimated_time_min": (
            distance / config.get("walking_speed_m_per_min", 75)
            + route_count * config.get("pick_handling_seconds", 12) / 60
        ),
        "whole_warehouse_utilization": used / capacity if capacity else 0.0,
        "allocated_bin_utilization": (
            used / selected_capacity if selected_capacity else 0.0
        ),
        "allocation_coverage": len(layout) / len(profile) if len(profile) else 0.0,
        "order_line_coverage": (
            float(profile_rows.Recorded_Order_Lines.sum()) / order_lines
            if order_lines
            else 0.0
        ),
        "unknown_hazard_attributes": int(
            (profile_rows.Hazard_Class == "UNSPECIFIED").sum()
        ),
    }


def compare(baseline, optimized):
    """Create a row-by-row metric comparison between two layouts."""

    # Store one comparison row for every metric appearing in either result.
    out = []
    for key in sorted(set(baseline) | set(optimized)):
        # Read the baseline and optimized values for this metric.
        base = baseline.get(key)
        improved = optimized.get(key)

        # Calculate a numeric change only when both values are real numbers.
        change = (
            improved - base
            if isinstance(improved, Real) and isinstance(base, Real)
            else None
        )

        # Append the comparison record.
        out.append(
            {
                "Metric": key,
                "Baseline": base,
                "Optimized": improved,
                "Change": change,
            }
        )

    # Return a table suitable for CSV export and dashboard display.
    return pd.DataFrame(out)
