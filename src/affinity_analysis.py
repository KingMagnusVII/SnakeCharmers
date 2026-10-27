"""Sparse, deterministic basket co-occurrence metrics."""
from __future__ import annotations  # Enables modern type-hint syntax.

from collections import Counter  # Counts SKU and pair occurrences.
from itertools import combinations  # Generates unique SKU pairs inside a basket.

import pandas as pd  # Provides DataFrame operations.

# Defines the exact columns returned by the affinity calculation.
AFFINITY_COLUMNS = [
    "SKU_A",
    "SKU_B",
    "Pair_Count",
    "Support",
    "SKU_A_Support",
    "SKU_B_Support",
    "Confidence_A_to_B",
    "Confidence_B_to_A",
    "Lift",
]


def compute_affinity(
    orders: pd.DataFrame,
    candidate_skus: set[str] | None = None,
    min_pair_count: int = 1,
    min_support: float = 0.0,
) -> pd.DataFrame:
    """Calculate observed unordered SKU pairs from distinct-SKU order baskets."""

    # Return an correctly shaped empty table when there is no input data.
    if orders.empty:
        return pd.DataFrame(columns=AFFINITY_COLUMNS)

    # Keep only the two columns needed to construct order baskets.
    selected = orders[["Order_ID", "SKU_ID"]].dropna().copy()

    # Optionally restrict the calculation to the active SKU assortment.
    if candidate_skus is not None:
        selected = selected.loc[selected["SKU_ID"].isin(candidate_skus)]

    # Group each order into a sorted list of unique SKUs.
    baskets = selected.groupby("Order_ID", sort=True)["SKU_ID"].apply(
        lambda values: sorted(set(values))
    )

    # Count how many distinct orders contain each SKU.
    item_orders = Counter(sku for basket in baskets for sku in basket)

    # Count how many distinct orders contain each unordered SKU pair.
    pair_counts = Counter(
        pair for basket in baskets for pair in combinations(basket, 2)
    )

    # The number of baskets is the denominator for support.
    n = len(baskets)
    if not n:
        return pd.DataFrame(columns=AFFINITY_COLUMNS)

    # Build one result record for every retained pair.
    rows = []
    for (a, b), count in pair_counts.items():
        support = count / n

        # Remove pairs that do not meet the configured thresholds.
        if count < min_pair_count or support < min_support:
            continue

        # Calculate individual SKU support values.
        a_support = item_orders[a] / n
        b_support = item_orders[b] / n

        # Store support, confidence, and lift metrics for the pair.
        rows.append(
            {
                "SKU_A": a,
                "SKU_B": b,
                "Pair_Count": count,
                "Support": support,
                "SKU_A_Support": a_support,
                "SKU_B_Support": b_support,
                "Confidence_A_to_B": count / item_orders[a],
                "Confidence_B_to_A": count / item_orders[b],
                "Lift": support / (a_support * b_support),
            }
        )

    # Construct the final DataFrame with stable column ordering.
    result = pd.DataFrame(rows, columns=AFFINITY_COLUMNS)

    # Sort deterministically so repeated runs produce the same ordering.
    if not result.empty:
        return result.sort_values(
            ["Pair_Count", "Lift", "SKU_A", "SKU_B"],
            ascending=[False, False, True, True],
            kind="mergesort",
        ).reset_index(drop=True)

    # Return the correctly shaped empty result when every pair was filtered.
    return result
