"""Metrics calculated from generated layouts and route records."""
from __future__ import annotations  # Enables modern type annotations.

from numbers import Real  # Lets comparison identify numeric metric values.

import pandas as pd  # Provides DataFrame operations.


def _completion_mask(routes: pd.DataFrame) -> pd.Series:
    """Return true for completed routes, including CSV-loaded string flags."""

    if routes.empty or "Complete" not in routes:
        return pd.Series(False, index=routes.index)
    return routes["Complete"].map(
        lambda value: value is True or str(value).strip().lower() == "true"
    )


def _complete_orders(routes: pd.DataFrame) -> int:
    """Count true completion flags consistently for bool or CSV string inputs."""

    return int(_completion_mask(routes).sum())


def evaluate(routes, layout, profile, locations, config):
    """Calculate route, utilization, coverage, and data-quality metrics."""

    route_count = len(routes)
    completion_mask = _completion_mask(routes)
    complete_orders = int(completion_mask.sum())
    incomplete_orders = route_count - complete_orders

    distance = float(routes["Distance_m"].sum()) if route_count else 0.0
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

    selected = locations[locations.Location_ID.isin(layout.Location_ID)]

    max_active_skus = int(config.get("max_active_skus", 200))
    active_fields = {"SKU_ID", "Physical_Metadata_Usable", "Recorded_Order_Lines"}
    if active_fields.issubset(profile.columns):
        active_profile = (
            profile.loc[profile["Physical_Metadata_Usable"].fillna(False).astype(bool)]
            .sort_values(
                ["Recorded_Order_Lines", "SKU_ID"],
                ascending=[False, True],
                kind="mergesort",
            )
            .head(max_active_skus)
        )
    else:
        active_profile = profile.head(max_active_skus)
    active_sku_ids = set(active_profile["SKU_ID"])
    active_assortment_count = len(active_sku_ids)
    allocated_active_count = (
        layout.loc[layout["SKU_ID"].isin(active_sku_ids), "SKU_ID"].nunique()
        if "SKU_ID" in layout.columns
        else 0
    )

    profile_rows = profile[profile.SKU_ID.isin(layout.SKU_ID)]
    capacity = float(locations.Volumetric_Capacity_cm3.sum())

    # Use observed inventory when available; otherwise use the configured
    # representative-stock assumption, matching the feasibility model.
    stock_units = pd.to_numeric(profile_rows["Inventory_Units"], errors="coerce").fillna(
        float(config.get("representative_inventory_units", 1))
    )
    used = float((profile_rows.Volume_cm3.fillna(0) * stock_units).sum())

    selected_capacity = float(selected.Volumetric_Capacity_cm3.sum())
    order_lines = float(profile.Recorded_Order_Lines.sum())

    unknown_hazard = profile_rows["Hazard_Class"].isna() | profile_rows["Hazard_Class"].astype(str).str.strip().str.upper().isin(["", "UNSPECIFIED", "UNKNOWN"])
    unknown_handling = profile_rows["Handling_Type"].isna() | profile_rows["Handling_Type"].astype(str).str.strip().str.upper().isin(["", "UNSPECIFIED", "UNKNOWN"])
    unknown_inventory = pd.to_numeric(profile_rows["Inventory_Units"], errors="coerce").isna()

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
        "active_assortment_sku_count": int(active_assortment_count),
        "active_assortment_allocated_sku_count": int(allocated_active_count),
        "active_assortment_unallocated_sku_count": int(
            max(active_assortment_count - allocated_active_count, 0)
        ),
        "active_assortment_coverage": (
            allocated_active_count / active_assortment_count
            if active_assortment_count
            else 0.0
        ),
        "order_line_coverage": (
            float(profile_rows.Recorded_Order_Lines.sum()) / order_lines
            if order_lines
            else 0.0
        ),
        "unknown_hazard_attributes": int(unknown_hazard.sum()),
        "unknown_handling_attributes": int(unknown_handling.sum()),
        "unknown_inventory_attributes": int(unknown_inventory.sum()),
    }


def compare(baseline, optimized):
    """Create a row-by-row metric comparison between two layouts."""
    out = []
    for key in sorted(set(baseline) | set(optimized)):
        base = baseline.get(key)
        improved = optimized.get(key)
        change = (
            improved - base
            if isinstance(improved, Real) and isinstance(base, Real)
            else None
        )
        out.append(
            {
                "Metric": key,
                "Baseline": base,
                "Optimized": improved,
                "Change": change,
            }
        )
    return pd.DataFrame(out)
