"""Walkable aisle approximation and deterministic multi-stop routes."""
from __future__ import annotations  # Enables modern type annotations.

import pandas as pd  # Provides DataFrame operations.


def select_fully_allocatable_orders(orders, layout, max_orders=500):
    """Select orders whose every SKU is present in the allocated assortment.

    This creates a clearly scoped fulfillment cohort for comparing layouts.
    Orders excluded from this cohort must still be measured separately against
    the full source-order sample; they must not be silently counted as complete.
    Pass max_orders=None to return every eligible order.
    """
    allocated_skus = set(layout["SKU_ID"].dropna())
    eligible_ids = []
    for order_id, group in orders.groupby("Order_ID", sort=True):
        sku_values = group["SKU_ID"]
        if sku_values.isna().any():
            continue
        order_skus = set(sku_values)
        if order_skus and order_skus.issubset(allocated_skus):
            eligible_ids.append(order_id)
            if max_orders is not None and len(eligible_ids) >= max_orders:
                break
    return orders[orders["Order_ID"].isin(eligible_ids)].copy()


def route_orders(orders, layout, locations, max_orders=500):
    """Build deterministic nearest-next-SKU routes using Manhattan distance."""

    # Join each assigned SKU to its warehouse coordinates and index by SKU.
    loc = (
        layout.merge(
            locations[["Location_ID", "X_m", "Y_m"]],
            on="Location_ID",
            how="left",
        )
        .set_index("SKU_ID")
    )

    # Store one route record per simulated order.
    records = []

    # Process orders in deterministic Order_ID order.
    for order_number, (order_id, group) in enumerate(
        orders.groupby("Order_ID", sort=True)
    ):
        # Count every source order toward the sample limit, including orders
        # whose SKUs are all unallocated.
        if order_number >= max_orders:
            break

        # Deduplicate repeated SKU lines within the same order.
        skus = list(dict.fromkeys(group.SKU_ID))

        # Keep only SKUs that exist in the proposed layout.
        present = [sku for sku in skus if sku in loc.index]
        if not present:
            records.append(
                {
                    "Order_ID": order_id,
                    "Visited_SKUs": "",
                    "Distance_m": 0.0,
                    "Complete": False,
                }
            )
            continue

        # Start at the dispatch depot origin.
        current = (0.0, 0.0)
        remaining = present[:]
        path = []
        distance = 0.0

        # Repeatedly visit the closest remaining SKU using Manhattan distance.
        while remaining:
            sku = min(
                remaining,
                key=lambda value: abs(loc.loc[value].X_m - current[0])
                + abs(loc.loc[value].Y_m - current[1]),
            )
            point = (loc.loc[sku].X_m, loc.loc[sku].Y_m)
            distance += abs(point[0] - current[0]) + abs(point[1] - current[1])
            path.append(sku)
            current = point
            remaining.remove(sku)

        # Add the return trip from the last SKU back to the depot.
        distance += abs(current[0]) + abs(current[1])

        # Record the route, total distance, and whether every SKU was assigned.
        records.append(
            {
                "Order_ID": order_id,
                "Visited_SKUs": "|".join(path),
                "Distance_m": distance,
                "Complete": len(present) == len(skus),
            }
        )

    # Convert all route records into a DataFrame for downstream evaluation.
    return pd.DataFrame(
        records,
        columns=["Order_ID", "Visited_SKUs", "Distance_m", "Complete"],
    )
