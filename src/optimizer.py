"""Demand-aware feasible improvement over the deterministic baseline."""
from __future__ import annotations  # Enables modern type annotations.

from collections import defaultdict

import pandas as pd  # Provides DataFrame operations.

from .feasibility import is_product_location_feasible, validate_layout  # Reuses placement constraints.
from .routing import route_orders  # Measures the project's deterministic route distance.


def _objective_weights(config):
    """Read the configured objective weights with safe zero defaults."""

    configured = config.get("objective_weights", {}) or {}
    return {
        name: float(configured.get(name, default))
        for name, default in {
            "distance": 1.0,
            "affinity": 0.0,
            "ergonomic": 0.0,
            "waste": 0.0,
        }.items()
    }


def _affinity_neighbors(affinity):
    """Build an undirected SKU graph weighted by observed pair counts."""

    neighbors = defaultdict(list)
    required = {"SKU_A", "SKU_B", "Pair_Count"}
    if affinity is None or affinity.empty or not required <= set(affinity.columns):
        return neighbors

    for row in affinity.itertuples(index=False):
        pair_count = pd.to_numeric(getattr(row, "Pair_Count"), errors="coerce")
        if pd.isna(pair_count) or pair_count <= 0:
            continue
        sku_a, sku_b = getattr(row, "SKU_A"), getattr(row, "SKU_B")
        if pd.isna(sku_a) or pd.isna(sku_b) or sku_a == sku_b:
            continue
        neighbors[sku_a].append((sku_b, float(pair_count)))
        neighbors[sku_b].append((sku_a, float(pair_count)))
    return neighbors


def _min_max_scale(values):
    """Scale a numeric series to 0..1, using zero for a constant series."""

    values = pd.to_numeric(values, errors="coerce").fillna(0.0)
    minimum, maximum = float(values.min()), float(values.max())
    if maximum <= minimum:
        return pd.Series(0.0, index=values.index)
    return (values - minimum) / (maximum - minimum)


def _coordinate_distance(first, second):
    """Use the project's Manhattan coordinate convention."""

    return abs(float(first.X_m) - float(second.X_m)) + abs(
        float(first.Y_m) - float(second.Y_m)
    )


def _affinity_costs(product_sku, candidates, used_locations, neighbors):
    """Return normalized proximity costs to already placed affinity neighbors."""

    linked = [
        (sku, strength)
        for sku, strength in neighbors.get(product_sku, [])
        if sku in used_locations
    ]
    if not linked:
        return pd.Series(0.0, index=candidates.index)

    distances = []
    for _, candidate in candidates.iterrows():
        weighted_distance = 0.0
        total_strength = 0.0
        for neighbor_sku, strength in linked:
            weighted_distance += strength * _coordinate_distance(
                candidate,
                used_locations[neighbor_sku],
            )
            total_strength += strength
        distances.append(weighted_distance / total_strength)
    return _min_max_scale(pd.Series(distances, index=candidates.index))


def _score_candidates(
    product_sku,
    product,
    candidates,
    used_locations,
    neighbors,
    config,
):
    """Score feasible candidates as a weighted sum of normalized costs."""

    weights = _objective_weights(config)
    scored = candidates.copy()
    scored["distance_cost"] = _min_max_scale(
        scored["Distance_to_Dispatch_Depot_m"]
    )
    scored["affinity_cost"] = _affinity_costs(
        product_sku,
        scored,
        used_locations,
        neighbors,
    )

    threshold = float(
        (config.get("ergonomics", {}) or {}).get("heavy_sku_weight_kg", 10.0)
    )
    maximum_level = max(float(scored["Shelf_Level"].max()), 1.0)
    weight = float(pd.to_numeric(product.Weight_kg, errors="coerce"))
    scored["ergonomic_cost"] = (
        scored["Shelf_Level"] / maximum_level if weight > threshold else 0.0
    )

    product_volume = pd.to_numeric(
        product.get("Volume_cm3"), errors="coerce"
    )
    if pd.isna(product_volume):
        product_volume = (
            float(product.Width_cm)
            * float(product.Height_cm)
            * float(product.Depth_cm)
        )
    capacity = pd.to_numeric(
        scored["Volumetric_Capacity_cm3"], errors="coerce"
    )
    scored["waste_cost"] = (1.0 - product_volume / capacity).clip(0.0, 1.0).fillna(0.0)
    scored["score"] = sum(
        weights[name] * scored[f"{name}_cost"]
        for name in ("distance", "affinity", "ergonomic", "waste")
    )
    return scored


def optimize_layout(profile, locations, baseline, affinity, config):
    """Greedily reassign each baseline SKU to a weighted feasible location."""

    # There is nothing to improve when the baseline has no assignments.
    if baseline.empty:
        return baseline.copy(), {"iterations": 0}

    # Index the profile by SKU so each baseline row can find its product data.
    profile_by_sku = profile.set_index("SKU_ID")
    neighbors = _affinity_neighbors(affinity)

    # Store optimized rows and prevent two SKUs from sharing one location.
    rows = []
    used = set()
    placed_locations = {}

    # Re-evaluate every baseline assignment independently.
    for row in baseline.itertuples(index=False):
        # Look up the physical and demand metadata for the SKU.
        product = profile_by_sku.loc[row.SKU_ID]

        # Only unused locations are candidates for this SKU.
        candidates = locations[~locations.Location_ID.isin(used)]

        # Remove every location that violates a known constraint.
        candidates = candidates[
            candidates.apply(
                lambda location: is_product_location_feasible(
                    product,
                    location,
                    config,
                ),
                axis=1,
            )
        ].copy()

        # A baseline assignment should always have at least one known-feasible replacement.
        if candidates.empty:
            raise ValueError(
                f"No known-feasible location remains for baseline SKU {row.SKU_ID}."
            )

        candidates = _score_candidates(
            row.SKU_ID,
            product,
            candidates,
            placed_locations,
            neighbors,
            config,
        )

        # Choose the best score, using Location_ID as a deterministic tie-breaker.
        location = candidates.sort_values(["score", "Location_ID"]).iloc[0]
        used.add(location.Location_ID)
        placed_locations[row.SKU_ID] = location

        # Save the optimized placement and its rationale.
        rows.append(
            {
                "SKU_ID": row.SKU_ID,
                "Location_ID": location.Location_ID,
                "Demand_Class": product.ABC_Class,
                "Placement_Rationale": "demand-weighted accessible feasible location",
            }
        )

    # Return the optimized layout and metadata describing the heuristic.
    result = pd.DataFrame(rows)
    return result, {
        "iterations": 1,
        "heuristic": "feasible weighted distance/affinity greedy reassignment",
        "objective_weights": _objective_weights(config),
        "affinity_pairs_available": int(len(affinity)) if affinity is not None else 0,
        "affinity_pairs_used": int(sum(len(values) for values in neighbors.values()) / 2),
    }


def improve_layout_by_route_distance(
    profile,
    locations,
    layout,
    orders,
    config,
    max_swap_attempts=100,
    max_passes=1,
    max_orders=500,
):
    """Improve a layout with deterministic feasible location swaps.

    The search keeps the assigned SKU set and occupied location set fixed. Each
    candidate swaps the locations of two assigned SKUs, rejects known feasibility
    violations, and accepts only a strict reduction in total route distance.
    """

    current = layout.copy().reset_index(drop=True)
    if current.empty:
        return current, {
            "starting_distance_m": 0.0,
            "final_distance_m": 0.0,
            "accepted_swaps": 0,
            "attempted_swaps": 0,
            "max_swap_attempts": int(max_swap_attempts),
            "max_passes": int(max_passes),
            "passes_completed": 0,
            "search_terminated_by_limit": False,
        }

    def route_distance(candidate):
        routes = route_orders(orders, candidate, locations, max_orders=max_orders)
        return float(routes["Distance_m"].sum()) if not routes.empty else 0.0

    def known_feasible(candidate):
        checks = validate_layout(candidate, profile, locations, config)
        return checks.empty or not (checks["Status"] == "VIOLATION").any()

    current_distance = route_distance(current)
    starting_distance = current_distance
    sku_order = sorted(current["SKU_ID"].tolist(), key=str)
    location_by_sku = current.set_index("SKU_ID")["Location_ID"].to_dict()
    attempted = 0
    accepted = 0
    passes_completed = 0

    for _ in range(max(0, int(max_passes))):
        if attempted >= int(max_swap_attempts):
            break
        best_layout = None
        best_distance = current_distance

        for index, first_sku in enumerate(sku_order):
            for second_sku in sku_order[index + 1 :]:
                if attempted >= int(max_swap_attempts):
                    break
                attempted += 1
                candidate = current.copy()
                first_location = location_by_sku[first_sku]
                second_location = location_by_sku[second_sku]
                candidate.loc[candidate["SKU_ID"] == first_sku, "Location_ID"] = second_location
                candidate.loc[candidate["SKU_ID"] == second_sku, "Location_ID"] = first_location

                if not known_feasible(candidate):
                    continue
                candidate_distance = route_distance(candidate)
                if candidate_distance < best_distance:
                    best_distance = candidate_distance
                    best_layout = candidate

            if attempted >= int(max_swap_attempts):
                break

        passes_completed += 1
        if best_layout is None:
            break

        current = best_layout
        current_distance = best_distance
        location_by_sku = current.set_index("SKU_ID")["Location_ID"].to_dict()
        accepted += 1

    return current, {
        "starting_distance_m": starting_distance,
        "final_distance_m": current_distance,
        "accepted_swaps": accepted,
        "attempted_swaps": attempted,
        "max_swap_attempts": int(max_swap_attempts),
        "max_passes": int(max_passes),
        "passes_completed": passes_completed,
        "search_terminated_by_limit": attempted >= int(max_swap_attempts),
    }
