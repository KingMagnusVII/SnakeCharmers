"""Metrics calculated from generated layouts and route records."""
from __future__ import annotations

from numbers import Real

import pandas as pd


def _complete_orders(routes: pd.DataFrame) -> int:
    """Count true completion flags consistently for bool or CSV string inputs."""
    if routes.empty or "Complete" not in routes:
        return 0
    return int(routes["Complete"].map(lambda value: value is True or str(value).strip().lower() == "true").sum())


def evaluate(routes, layout, profile, locations, config):
    route_count = len(routes)
    distance = float(routes["Distance_m"].sum()) if route_count else 0.0
    selected = locations[locations.Location_ID.isin(layout.Location_ID)]
    profile_rows = profile[profile.SKU_ID.isin(layout.SKU_ID)]
    capacity = float(locations.Volumetric_Capacity_cm3.sum())
    used = float(profile_rows.Volume_cm3.fillna(0).sum())
    selected_capacity = float(selected.Volumetric_Capacity_cm3.sum())
    order_lines = float(profile.Recorded_Order_Lines.sum())
    return {
        "orders_simulated": int(route_count),
        "complete_orders": _complete_orders(routes),
        "total_distance_m": distance,
        "average_distance_m": distance / route_count if route_count else 0.0,
        "estimated_time_min": distance / config.get("walking_speed_m_per_min", 75) + route_count * config.get("pick_handling_seconds", 12) / 60,
        "whole_warehouse_utilization": used / capacity if capacity else 0.0,
        "allocated_bin_utilization": used / selected_capacity if selected_capacity else 0.0,
        "allocation_coverage": len(layout) / len(profile) if len(profile) else 0.0,
        "order_line_coverage": float(profile_rows.Recorded_Order_Lines.sum()) / order_lines if order_lines else 0.0,
        "unknown_hazard_attributes": int((profile_rows.Hazard_Class == "UNSPECIFIED").sum()),
    }


def compare(baseline, optimized):
    out = []
    for key in sorted(set(baseline) | set(optimized)):
        base, improved = baseline.get(key), optimized.get(key)
        out.append({"Metric": key, "Baseline": base, "Optimized": improved, "Change": improved - base if isinstance(improved, Real) and isinstance(base, Real) else None})
    return pd.DataFrame(out)
