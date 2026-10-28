"""Walkable aisle approximation and deterministic multi-stop routes."""
from __future__ import annotations  # Enables modern type annotations.

import pandas as pd  # Provides DataFrame operations.


def route_orders(orders, layout, locations, max_orders=500, include_zero_pick_orders=False):
    """Build deterministic nearest-next-SKU routes using Manhattan distance.

    By default, preserve the historical metric: collect up to ``max_orders``
    orders that have at least one SKU in the layout. Set
    ``include_zero_pick_orders=True`` to instead count every source order,
    including orders with no allocated SKUs, within the first ``max_orders``.
    """

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

    # Process orders in deterministic Order_ID order. The historical sample
    # counts only orders with at least one pickable SKU; source-order coverage
    # can opt into counting zero-pick orders as well.
    for order_id, group in orders.groupby("Order_ID", sort=True):
        if len(records) >= max_orders:
            break

        # Deduplicate repeated SKU lines within the same order.
        skus = list(dict.fromkeys(group.SKU_ID))

        # Keep only SKUs that exist in the proposed layout.
        present = [sku for sku in skus if sku in loc.index]
        if not present:
            if include_zero_pick_orders:
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
