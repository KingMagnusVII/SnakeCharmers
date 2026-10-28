"""Deterministic constrained baseline allocation."""
from __future__ import annotations  # Enables modern type annotations.

import pandas as pd  # Provides DataFrame operations.

from .demand_analysis import product_dimensional_fit  # Reuses the dimensional-fit calculation.
from .feasibility import fits_product, is_product_location_feasible, modeled_stock_load_kg, rack_load_fits  # Reuses dimensional and hard-constraint checks.


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
        .head(max(0, max_skus))
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
        def score(sku: str) -> tuple[float, int, int, int]:
            order_indexes = candidate_orders[sku]
            # Greedily maximize marginal order coverage. A SKU receives a
            # larger share of credit as the remaining SKUs in an order are
            # selected, so multi-SKU orders can be completed by later picks.
            coverage_gain = sum(
                1.0 / order_remaining[index]
                for index in order_indexes
                if order_remaining[index] > 0
            )
            potential = len(order_indexes)
            row = metadata[sku]
            return (
                coverage_gain,
                potential,
                int(row.get("Distinct_Orders", 0)),
                int(row.get("Recorded_Order_Lines", 0)),
            )

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

    usable = profile[profile.Physical_Metadata_Usable].copy()
    eligible = (
        select_feasible_candidates(profile, locations, config)
        if candidates is None
        else candidates.copy()
    )

    used = set()
    rack_loads: dict[str, float] = {}
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

    ordered = eligible.sort_values(
        ["Width_cm", "Height_cm", "Depth_cm", "SKU_ID"],
        ascending=[False, False, False, True],
    )

    for _, product in ordered.iterrows():
        choices = locations[~locations.Location_ID.isin(used)]

        if "Location_Type" in locations.columns:
            standard_locations = locations[locations.Location_Type != "OVERSIZED"]
            if not standard_locations.empty and standard_locations.apply(
                lambda location: fits_product(
                    product, location, bool(config.get("allow_rotations", True))
                ),
                axis=1,
            ).any():
                choices = choices[choices.Location_Type != "OVERSIZED"]

        match = choices[
            choices.apply(
                lambda location: is_product_location_feasible(product, location, config)
                and rack_load_fits(product, location, rack_loads, config),
                axis=1,
            )
        ].sort_values("Location_ID")

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

        location = match.iloc[0]
        used.add(location.Location_ID)
        rack_load = modeled_stock_load_kg(product, config)
        if rack_load is not None:
            rack_id = location.get("Rack_ID")
            rack_loads[rack_id] = rack_loads.get(rack_id, 0.0) + rack_load

        rows.append(
            {
                "SKU_ID": product.SKU_ID,
                "Location_ID": location.Location_ID,
                "Demand_Class": product.ABC_Class,
                "Placement_Rationale": "deterministic constrained-first baseline",
            }
        )

    return (
        pd.DataFrame(rows, columns=["SKU_ID", "Location_ID", "Demand_Class", "Placement_Rationale"]),
        pd.DataFrame(excluded, columns=["SKU_ID", "Reason"]),
    )
