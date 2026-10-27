"""Deterministic constrained baseline allocation."""
from __future__ import annotations  # Enables modern type annotations.

import pandas as pd  # Provides DataFrame operations.

from .demand_analysis import product_dimensional_fit  # Reuses the dimensional-fit calculation.
from .feasibility import fits_product, is_product_location_feasible  # Reuses dimensional and hard-constraint checks.


def select_feasible_candidates(
    profile: pd.DataFrame,
    locations: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """Select demand-ranked SKUs that fit at least one configured location."""

    max_skus = int(config.get("max_active_skus", 200))
    usable = profile[profile.Physical_Metadata_Usable].copy()
    dimensional_fit = product_dimensional_fit(
        usable,
        locations,
        allow_rotations=bool(config.get("allow_rotations", True)),
    )
    feasible_ids = set(
        dimensional_fit.loc[dimensional_fit.Fit_Location_Count > 0, "SKU_ID"]
    )
    return (
        usable[usable.SKU_ID.isin(feasible_ids)]
        .sort_values(
            ["Recorded_Order_Lines", "SKU_ID"],
            ascending=[False, True],
        )
        .head(max_skus)
        .copy()
    )


def select_order_coverage_candidates(
    profile: pd.DataFrame,
    locations: pd.DataFrame,
    orders: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """Select feasible SKUs greedily by newly completed whole orders.

    This is a comparison strategy only; the demand-ranked selector remains the
    default. At each step, choose the SKU that completes the most previously
    incomplete orders, then use order incidence, recorded lines, and SKU ID as
    deterministic tie-breakers.
    """

    max_skus = int(config.get("max_active_skus", 200))
    usable = profile[profile.Physical_Metadata_Usable].copy()
    dimensional_fit = product_dimensional_fit(
        usable,
        locations,
        allow_rotations=bool(config.get("allow_rotations", True)),
    )
    feasible_ids = set(
        dimensional_fit.loc[dimensional_fit.Fit_Location_Count > 0, "SKU_ID"]
    )
    feasible = usable[usable.SKU_ID.isin(feasible_ids)].copy()
    if max_skus <= 0 or feasible.empty:
        return feasible.iloc[0:0].copy()

    grouped_orders = (
        orders.loc[orders["Order_ID"].notna() & orders["SKU_ID"].notna()]
        .groupby("Order_ID", sort=True)["SKU_ID"]
        .agg(lambda values: frozenset(values))
    )
    feasible_set = set(feasible.SKU_ID)
    order_sets = [items for items in grouped_orders if items and items <= feasible_set]
    order_remaining = {index: len(items) for index, items in enumerate(order_sets)}
    candidate_orders = {sku: [] for sku in feasible_set}
    for index, items in enumerate(order_sets):
        for sku in items:
            candidate_orders[sku].append(index)

    remaining = set(feasible_set)
    metadata = feasible.set_index("SKU_ID").to_dict("index")
    for sku in metadata:
        metadata[sku]["SKU_ID"] = sku
    rows = []
    while remaining and len(rows) < max_skus:
        def score(sku: str) -> tuple[int, int, int, int]:
            order_indexes = candidate_orders[sku]
            completed = sum(order_remaining[index] == 1 for index in order_indexes)
            potential = len(order_indexes)
            row = metadata[sku]
            return (
                completed,
                potential,
                int(row.get("Distinct_Orders", 0)),
                int(row.get("Recorded_Order_Lines", 0)),
            )

        # Apply the final tie-break in ascending SKU order without relying on
        # unordered set iteration.
        best_score = max(score(sku) for sku in remaining)
        chosen = min(sku for sku in remaining if score(sku) == best_score)
        rows.append(metadata[chosen])
        for index in candidate_orders[chosen]:
            order_remaining[index] -= 1
        remaining.remove(chosen)

    return pd.DataFrame(rows, columns=feasible.columns).reset_index(drop=True)
def allocate_baseline(
    profile: pd.DataFrame,
    locations: pd.DataFrame,
    config: dict,
    candidates: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate eligible SKUs to feasible locations deterministically."""

    # Select dimensionally feasible products before applying the assortment cap.
    usable = profile[profile.Physical_Metadata_Usable].copy()
    eligible = (
        select_feasible_candidates(profile, locations, config)
        if candidates is None
        else candidates.copy()
    )

    # Track occupied locations and products that could not be placed.
    used = set()
    rows = []
    excluded = []

    selected_ids = set(eligible.SKU_ID)
    dimensional_fit = product_dimensional_fit(
        usable,
        locations,
        allow_rotations=bool(config.get("allow_rotations", True)),
    ).set_index("SKU_ID")
    for _, product in usable[~usable.SKU_ID.isin(selected_ids)].iterrows():
        if dimensional_fit.loc[product.SKU_ID, "Fit_Location_Count"] == 0:
            excluded.append(
                {
                    "SKU_ID": product.SKU_ID,
                    "Reason": "dimensional_infeasible",
                }
            )

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
    return (
        pd.DataFrame(rows, columns=["SKU_ID", "Location_ID", "Demand_Class", "Placement_Rationale"]),
        pd.DataFrame(excluded, columns=["SKU_ID", "Reason"]),
    )
