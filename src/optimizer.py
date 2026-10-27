"""Demand-aware feasible improvement over the deterministic baseline."""
from __future__ import annotations  # Enables modern type annotations.

import pandas as pd  # Provides DataFrame operations.

from .feasibility import is_product_location_feasible  # Reuses placement constraints.


def optimize_layout(profile, locations, baseline, affinity, config):
    """Greedily reassign each baseline SKU to an accessible feasible location."""

    # There is nothing to improve when the baseline has no assignments.
    if baseline.empty:
        return baseline.copy(), {"iterations": 0}

    # Index the profile by SKU so each baseline row can find its product data.
    profile_by_sku = profile.set_index("SKU_ID")

    # Store optimized rows and prevent two SKUs from sharing one location.
    rows = []
    used = set()

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

        # Prefer short dispatch distance; heavy products also prefer low shelves.
        candidates["score"] = (
            candidates["Distance_to_Dispatch_Depot_m"]
            + candidates["Shelf_Level"]
            * (0.5 if product.Weight_kg > 10 else 0)
        )

        # Choose the best score, using Location_ID as a deterministic tie-breaker.
        location = candidates.sort_values(["score", "Location_ID"]).iloc[0]
        used.add(location.Location_ID)

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
        "heuristic": "feasible demand/distance greedy reassignment",
    }
