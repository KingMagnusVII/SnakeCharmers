"""Affinity-aware feasible improvement over the deterministic baseline."""
from __future__ import annotations  # Enables modern type annotations.

import math  # Provides stable logarithmic affinity weighting.

import pandas as pd  # Provides DataFrame operations.

from .feasibility import is_product_location_feasible  # Reuses placement constraints.


def _affinity_index(affinity: pd.DataFrame) -> dict[str, list[tuple[str, float]]]:
    """Build a symmetric SKU -> (related SKU, strength) lookup from affinity data."""

    if affinity.empty:
        return {}

    required = {"SKU_A", "SKU_B", "Pair_Count", "Lift"}
    if not required.issubset(affinity.columns):
        return {}

    index: dict[str, list[tuple[str, float]]] = {}
    for row in affinity.itertuples(index=False):
        try:
            pair_count = float(row.Pair_Count)
            lift = float(row.Lift)
        except (TypeError, ValueError):
            continue

        if pair_count <= 0 or not math.isfinite(lift) or lift <= 0:
            continue

        # Log scaling prevents a single very large lift from dominating the score.
        strength = math.log1p(pair_count) * math.log1p(lift)
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
    """Return normalized affinity to already-placed related SKUs.

    A related SKU scores highest when it is already close to the candidate bin.
    """

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

    if baseline.empty:
        return baseline.copy(), {"iterations": 0}

    profile_by_sku = profile.set_index("SKU_ID")
    affinity_index = _affinity_index(affinity)
    placed_locations: dict[str, pd.Series] = {}
    rows = []
    used = set()

    distance_weight = float(config.get("objective_weights", {}).get("distance", 1.0))
    affinity_weight = float(config.get("objective_weights", {}).get("affinity", 0.25))
    ergonomic_weight = float(config.get("objective_weights", {}).get("ergonomic", 0.1))

    max_distance = float(locations["Distance_to_Dispatch_Depot_m"].max()) if not locations.empty else 0.0
    max_distance = max(max_distance, 1.0)

    # ML forecast now affects the optimized layout itself: high predicted-demand
    # SKUs are placed first, giving them first access to the best feasible bins.
    # The baseline order remains historical-demand based, so the two strategies
    # can still be compared fairly.
    if "Predicted_Next_Week_Demand" in profile.columns:
        ml_priority = profile_by_sku["Predicted_Next_Week_Demand"].reindex(baseline.SKU_ID)
        ml_priority = pd.to_numeric(ml_priority, errors="coerce").fillna(0.0)
        baseline = baseline.assign(_ml_priority=baseline.SKU_ID.map(ml_priority))
        baseline = baseline.sort_values(
            ["_ml_priority", "SKU_ID"], ascending=[False, True]
        ).drop(columns="_ml_priority")
        ml_used = True
    else:
        # Keep the optimizer usable for older profiles that do not contain ML data.
        ml_used = False

    for row in baseline.itertuples(index=False):
        product = profile_by_sku.loc[row.SKU_ID]
        candidates = locations[~locations.Location_ID.isin(used)]
        candidates = candidates[
            candidates.apply(
                lambda location: is_product_location_feasible(product, location, config),
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
            # Scale the normalized affinity bonus to the warehouse distance range so
            # the configured objective weights are comparable in magnitude.
            affinity_bonus = affinity * max_distance
            return (
                distance_weight * distance
                + ergonomic_weight * heavy_penalty
                - affinity_weight * affinity_bonus
            )

        candidates["score"] = candidates.apply(score, axis=1)
        location = candidates.sort_values(["score", "Location_ID"]).iloc[0]
        used.add(location.Location_ID)
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
    }
