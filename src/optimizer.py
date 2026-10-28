"""Affinity-aware feasible improvement over the deterministic baseline."""
from __future__ import annotations

import math

import pandas as pd

from .feasibility import fits_product, is_product_location_feasible, modeled_stock_load_kg, rack_load_fits, validate_layout
from .routing import route_orders


def _affinity_index(affinity: pd.DataFrame | None) -> dict[str, list[tuple[str, float]]]:
    """Build a symmetric SKU -> (related SKU, strength) lookup from affinity data.

    Older/main-branch affinity inputs may contain only SKU_A, SKU_B and
    Pair_Count. When Lift is available, preserve the richer Magnus weighting;
    otherwise use pair count as a deterministic strength signal.
    """
    if affinity is None or affinity.empty:
        return {}
    required = {"SKU_A", "SKU_B", "Pair_Count"}
    if not required.issubset(affinity.columns):
        return {}
    has_lift = "Lift" in affinity.columns
    index: dict[str, list[tuple[str, float]]] = {}
    for row in affinity.itertuples(index=False):
        try:
            pair_count = float(row.Pair_Count)
            lift = float(getattr(row, "Lift", 1.0)) if has_lift else 1.0
        except (TypeError, ValueError):
            continue
        if pair_count <= 0 or not math.isfinite(lift) or lift <= 0:
            continue
        strength = math.log1p(pair_count) * math.log1p(lift) if has_lift else math.log1p(pair_count)
        index.setdefault(row.SKU_A, []).append((row.SKU_B, strength))
        index.setdefault(row.SKU_B, []).append((row.SKU_A, strength))
    return index


def _affinity_score(
    sku: str,
    candidate: pd.Series,
    placed_locations: dict[str, pd.Series],
    affinity_index: dict[str, list[tuple[str, float]]],
    max_distance: float,
) -> float:
    """Return normalized affinity to already-placed related SKUs."""
    related = affinity_index.get(sku, [])
    if not related or max_distance <= 0:
        return 0.0
    weighted_proximity = 0.0
    total_strength = 0.0
    for other_sku, strength in related:
        other = placed_locations.get(other_sku)
        if other is None:
            continue
        distance = abs(float(candidate["X_m"]) - float(other["X_m"])) + abs(
            float(candidate["Y_m"]) - float(other["Y_m"])
        )
        proximity = max(0.0, 1.0 - distance / max_distance)
        weighted_proximity += strength * proximity
        total_strength += strength
    if total_strength == 0:
        return 0.0
    return weighted_proximity / total_strength


def optimize_layout(profile, locations, baseline, affinity, config):
    """Greedily reassign each SKU to a feasible location using ML, distance and affinity."""
    objective_weights = dict(config.get("objective_weights", {}))
    objective_weights.setdefault("distance", 1.0)
    objective_weights.setdefault("affinity", 0.25)
    objective_weights.setdefault("ergonomic", 0.1)
    objective_weights.setdefault("waste", 0.00001)

    if baseline.empty:
        return baseline.copy(), {"iterations": 0, "objective_weights": objective_weights}

    profile_by_sku = profile.set_index("SKU_ID")
    affinity_index = _affinity_index(affinity)
    placed_locations: dict[str, pd.Series] = {}
    rows = []
    used = set()
    rack_loads: dict[str, float] = {}

    distance_weight = float(objective_weights["distance"])
    affinity_weight = float(objective_weights["affinity"])
    ergonomic_weight = float(objective_weights["ergonomic"])

    max_distance = float(locations["Distance_to_Dispatch_Depot_m"].max()) if not locations.empty else 0.0
    max_distance = max(max_distance, 1.0)

    if "Predicted_Next_Week_Demand" in profile.columns:
        ml_priority = profile_by_sku["Predicted_Next_Week_Demand"].reindex(baseline.SKU_ID)
        ml_priority = pd.to_numeric(ml_priority, errors="coerce").fillna(0.0)
        baseline = baseline.assign(_ml_priority=baseline.SKU_ID.map(ml_priority))
        baseline = baseline.sort_values(
            ["_ml_priority", "SKU_ID"], ascending=[False, True]
        ).drop(columns="_ml_priority")
        ml_used = True
    else:
        ml_used = False

    for row in baseline.itertuples(index=False):
        product = profile_by_sku.loc[row.SKU_ID]
        candidates = locations[~locations.Location_ID.isin(used)]

        if "Location_Type" in locations.columns:
            standard_locations = locations[locations.Location_Type != "OVERSIZED"]
            if not standard_locations.empty and standard_locations.apply(
                lambda location: fits_product(
                    product, location, bool(config.get("allow_rotations", True))
                ),
                axis=1,
            ).any():
                candidates = candidates[candidates.Location_Type != "OVERSIZED"]

        candidates = candidates[
            candidates.apply(
                lambda location: is_product_location_feasible(product, location, config)
                and rack_load_fits(product, location, rack_loads, config),
                axis=1,
            )
        ].copy()

        if candidates.empty:
            raise ValueError(f"No known-feasible location remains for baseline SKU {row.SKU_ID}.")

        def score(location: pd.Series) -> float:
            distance = float(location["Distance_to_Dispatch_Depot_m"])
            heavy_penalty = float(location["Shelf_Level"]) * (0.5 if product.Weight_kg > 10 else 0.0)
            affinity = _affinity_score(
                row.SKU_ID,
                location,
                placed_locations,
                affinity_index,
                max_distance,
            )
            affinity_bonus = affinity * max_distance
            return (
                distance_weight * distance
                + ergonomic_weight * heavy_penalty
                - affinity_weight * affinity_bonus
            )

        candidates["score"] = candidates.apply(score, axis=1)
        location = candidates.sort_values(["score", "Location_ID"]).iloc[0]
        used.add(location.Location_ID)
        rack_load = modeled_stock_load_kg(product, config)
        if rack_load is not None:
            rack_id = location.get("Rack_ID")
            rack_loads[rack_id] = rack_loads.get(rack_id, 0.0) + rack_load
        placed_locations[row.SKU_ID] = location

        affinity_used = _affinity_score(
            row.SKU_ID,
            location,
            placed_locations,
            affinity_index,
            max_distance,
        )
        rationale = "feasible distance/ergonomic greedy placement"
        if ml_used:
            rationale += " with ML demand priority"
        if affinity_used > 0:
            rationale += " and affinity-aware co-location"

        rows.append(
            {
                "SKU_ID": row.SKU_ID,
                "Location_ID": location.Location_ID,
                "Demand_Class": product.ABC_Class,
                "Placement_Rationale": rationale,
            }
        )

    result = pd.DataFrame(rows)
    return result, {
        "iterations": 1,
        "heuristic": "feasible ML-priority distance/ergonomic greedy reassignment with affinity",
        "ml_demand_priority_used": ml_used,
        "affinity_pairs_used": sum(1 for sku in affinity_index if sku in placed_locations),
        "objective_weights": objective_weights,
    }


def improve_layout_by_route_distance(
    profile: pd.DataFrame,
    locations: pd.DataFrame,
    layout: pd.DataFrame,
    orders: pd.DataFrame,
    config: dict,
    max_swap_attempts: int = 100,
    max_passes: int = 1,
    max_orders: int = 500,
) -> tuple[pd.DataFrame, dict]:
    """Improve a layout with deterministic feasible location swaps."""
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
