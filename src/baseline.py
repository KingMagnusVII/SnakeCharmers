"""Deterministic constrained baseline allocation."""
from __future__ import annotations  # Enables modern type annotations.

import pandas as pd  # Provides DataFrame operations.

from .feasibility import is_product_location_feasible  # Reuses hard-constraint checks.


def allocate_baseline(
    profile: pd.DataFrame,
    locations: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate eligible SKUs to feasible locations deterministically."""

    # Limit the active assortment to the configured number of SKUs.
    max_skus = int(config.get("max_active_skus", 200))

    # Keep only products with usable physical metadata and rank by demand.
    eligible = (
        profile[profile.Physical_Metadata_Usable]
        .sort_values(
            ["Recorded_Order_Lines", "SKU_ID"],
            ascending=[False, True],
        )
        .head(max_skus)
        .copy()
    )

    # Track occupied locations and products that could not be placed.
    used = set()
    rows = []
    excluded = []

    # Place larger products first so they have the widest choice of bins.
    ordered = eligible.sort_values(
        ["Width_cm", "Height_cm", "Depth_cm", "SKU_ID"],
        ascending=[False, False, False, True],
    )

    for _, product in ordered.iterrows():
        # Only locations not already assigned to another SKU are candidates.
        choices = locations[~locations.Location_ID.isin(used)]

        # Apply the same feasibility rules used by the independent validator.
        match = choices[
            choices.apply(
                lambda location: is_product_location_feasible(
                    product,
                    location,
                    config,
                ),
                axis=1,
            )
        ].sort_values("Location_ID")

        # Record products that have no remaining feasible location.
        if match.empty:
            excluded.append(
                {
                    "SKU_ID": product.SKU_ID,
                    "Reason": "infeasible_or_no_remaining_location",
                }
            )
            continue

        # Choose the first deterministic feasible location.
        location = match.iloc[0]
        used.add(location.Location_ID)

        # Save the allocation and explain why it was chosen.
        rows.append(
            {
                "SKU_ID": product.SKU_ID,
                "Location_ID": location.Location_ID,
                "Demand_Class": product.ABC_Class,
                "Placement_Rationale": "deterministic constrained-first baseline",
            }
        )

    # Return both successful allocations and excluded products.
    return pd.DataFrame(rows), pd.DataFrame(excluded)
