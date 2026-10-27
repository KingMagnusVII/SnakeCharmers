"""Deterministic constrained baseline allocation."""
from __future__ import annotations  # Enables modern type annotations.

import pandas as pd  # Provides DataFrame operations.

from .feasibility import fits_product, is_product_location_feasible  # Reuses dimensional and hard-constraint checks.


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

        # Reserve dedicated oversized slots for products that do not fit any
        # standard bin. The 240 standard bins provide ample capacity for the
        # configured active assortment, so normal SKUs should not consume them.
        if "Location_Type" in locations.columns:
            standard_locations = locations[locations.Location_Type != "OVERSIZED"]
            if not standard_locations.empty and standard_locations.apply(
                lambda location: fits_product(
                    product, location, bool(config.get("allow_rotations", True))
                ),
                axis=1,
            ).any():
                choices = choices[choices.Location_Type != "OVERSIZED"]

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

        # Explain whether a product cannot fit any bin or failed remaining constraints.
        if match.empty:
            allow_rotations = bool(config.get("allow_rotations", True))
            dimensional_matches = locations[
                locations.apply(
                    lambda location: fits_product(product, location, allow_rotations),
                    axis=1,
                )
            ]
            reason = (
                "does_not_fit_any_bin_dimensions"
                if dimensional_matches.empty
                else "no_remaining_feasible_location"
            )
            excluded.append({"SKU_ID": product.SKU_ID, "Reason": reason})
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
