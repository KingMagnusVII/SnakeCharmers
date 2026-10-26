"""Sparse, deterministic basket co-occurrence metrics."""
from __future__ import annotations
from itertools import combinations
from collections import Counter
import pandas as pd

AFFINITY_COLUMNS = ["SKU_A", "SKU_B", "Pair_Count", "Support", "SKU_A_Support", "SKU_B_Support", "Confidence_A_to_B", "Confidence_B_to_A", "Lift"]

def compute_affinity(orders: pd.DataFrame, candidate_skus: set[str] | None = None, min_pair_count: int = 1, min_support: float = 0.0) -> pd.DataFrame:
    """Calculate observed unordered pairs from distinct-SKU order baskets."""
    if orders.empty:
        return pd.DataFrame(columns=AFFINITY_COLUMNS)
    selected = orders[["Order_ID", "SKU_ID"]].dropna().copy()
    if candidate_skus is not None:
        selected = selected.loc[selected["SKU_ID"].isin(candidate_skus)]
    baskets = selected.groupby("Order_ID", sort=True)["SKU_ID"].apply(lambda x: sorted(set(x)))
    item_orders = Counter(sku for basket in baskets for sku in basket)
    pair_counts = Counter(pair for basket in baskets for pair in combinations(basket, 2))
    n = len(baskets)
    if not n:
        return pd.DataFrame(columns=AFFINITY_COLUMNS)
    rows = []
    for (a, b), count in pair_counts.items():
        support = count / n
        if count < min_pair_count or support < min_support:
            continue
        a_support, b_support = item_orders[a] / n, item_orders[b] / n
        rows.append({"SKU_A": a, "SKU_B": b, "Pair_Count": count, "Support": support, "SKU_A_Support": a_support, "SKU_B_Support": b_support, "Confidence_A_to_B": count / item_orders[a], "Confidence_B_to_A": count / item_orders[b], "Lift": support / (a_support * b_support)})
    result = pd.DataFrame(rows, columns=AFFINITY_COLUMNS)
    return result.sort_values(["Pair_Count", "Lift", "SKU_A", "SKU_B"], ascending=[False, False, True, True], kind="mergesort").reset_index(drop=True) if not result.empty else result
