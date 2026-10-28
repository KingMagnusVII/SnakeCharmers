"""Chronological inventory estimation and stock-aware order replay.

Olist has historical order-item lines, not an on-hand inventory snapshot. All
quantities produced here are simulated line-count proxies, never observed stock.
"""
from __future__ import annotations

import math
import pandas as pd

from .routing import route_orders


def chronological_train_test_split(
    orders: pd.DataFrame, train_fraction: float = 0.8
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Split whole orders at a timestamp boundary, with training strictly earlier."""
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be strictly between 0 and 1.")
    required = {"Order_ID", "Timestamp"}
    if not required.issubset(orders.columns):
        raise ValueError(f"orders must include columns: {sorted(required)}")
    valid = orders.loc[orders["Order_ID"].notna()].copy()
    valid["Timestamp"] = pd.to_datetime(valid["Timestamp"], errors="coerce")
    valid = valid.loc[valid["Timestamp"].notna()]
    times = pd.Index(valid["Timestamp"].drop_duplicates().sort_values())
    if len(times) < 2:
        raise ValueError("At least two distinct order timestamps are needed for a chronological split.")
    split_index = max(1, min(len(times) - 1, int(len(times) * train_fraction)))
    cutoff = pd.Timestamp(times[split_index])
    train = valid.loc[valid["Timestamp"] < cutoff].copy()
    test = valid.loc[valid["Timestamp"] >= cutoff].copy()
    if train.empty or test.empty:
        raise ValueError("Chronological split produced an empty training or test partition.")
    if train["Timestamp"].max() >= test["Timestamp"].min():
        raise AssertionError("Chronological leakage: training timestamps overlap test timestamps.")
    return train, test, cutoff


def estimate_starting_inventory(
    training_orders: pd.DataFrame, coverage_days: int = 14
) -> tuple[pd.DataFrame, int]:
    """Estimate per-SKU starting stock as ceil(train daily line rate × coverage days)."""
    if coverage_days <= 0:
        raise ValueError("coverage_days must be a positive integer.")
    valid = training_orders.loc[
        training_orders["SKU_ID"].notna() & training_orders["Timestamp"].notna()
    ].copy()
    if valid.empty:
        return pd.DataFrame(columns=[
            "SKU_ID", "Training_Order_Lines", "Training_Days",
            "Estimated_Daily_Demand", "Coverage_Days", "Starting_Inventory_Units",
        ]), 0
    valid["Timestamp"] = pd.to_datetime(valid["Timestamp"], errors="coerce")
    valid = valid.loc[valid["Timestamp"].notna()]
    if valid.empty:
        return pd.DataFrame(columns=[
            "SKU_ID", "Training_Order_Lines", "Training_Days",
            "Estimated_Daily_Demand", "Coverage_Days", "Starting_Inventory_Units",
        ]), 0
    training_days = max(1, int((valid["Timestamp"].max().normalize() - valid["Timestamp"].min().normalize()).days) + 1)
    if "Quantity" in valid:
        quantities = pd.to_numeric(valid["Quantity"], errors="coerce").fillna(1.0).clip(lower=0)
        valid = valid.assign(_quantity=quantities)
        demand = valid.groupby("SKU_ID", as_index=False)["_quantity"].sum().rename(
            columns={"_quantity": "Training_Order_Lines"}
        )
    else:
        demand = valid.groupby("SKU_ID", as_index=False).size().rename(
            columns={"size": "Training_Order_Lines"}
        )
    demand["Estimated_Daily_Demand"] = demand["Training_Order_Lines"] / training_days
    demand["Coverage_Days"] = int(coverage_days)
    demand["Starting_Inventory_Units"] = demand["Estimated_Daily_Demand"].map(
        lambda rate: max(1, int(math.ceil(float(rate) * coverage_days)))
    )
    return demand.sort_values("SKU_ID", kind="mergesort").reset_index(drop=True), training_days


def simulate_inventory_picking(
    test_orders: pd.DataFrame,
    layout: pd.DataFrame,
    locations: pd.DataFrame,
    inventory_estimates: pd.DataFrame,
    max_orders: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Replay orders chronologically; fulfill atomically or record stockout/unallocated lines.

    Only fully fulfillable orders deplete inventory and incur a pick route. Both
    baseline and optimized layouts should be passed the same orders and starting
    inventory estimates for a fair comparison.
    """
    required = {"Order_ID", "SKU_ID", "Timestamp"}
    if not required.issubset(test_orders.columns):
        raise ValueError(f"test_orders must include columns: {sorted(required)}")
    valid = test_orders.loc[test_orders["Order_ID"].notna()].copy()
    valid["Timestamp"] = pd.to_datetime(valid["Timestamp"], errors="coerce")
    order_index = valid[["Order_ID", "Timestamp"]].drop_duplicates("Order_ID")
    order_index = order_index.sort_values(["Timestamp", "Order_ID"], kind="mergesort", na_position="last")
    if max_orders is not None and int(max_orders) > 0:
        selected_ids = set(order_index.head(int(max_orders))["Order_ID"])
        valid = valid.loc[valid["Order_ID"].isin(selected_ids)].copy()
        order_index = order_index.loc[order_index["Order_ID"].isin(selected_ids)].copy()

    estimates = inventory_estimates.copy()
    if not {"SKU_ID", "Starting_Inventory_Units"}.issubset(estimates.columns):
        raise ValueError("inventory_estimates must include SKU_ID and Starting_Inventory_Units.")
    initial = {
        row.SKU_ID: max(0, int(row.Starting_Inventory_Units))
        for row in estimates[["SKU_ID", "Starting_Inventory_Units"]].itertuples(index=False)
    }
    remaining = dict(initial)
    layout_skus = set(layout["SKU_ID"]) if "SKU_ID" in layout else set()
    stockout_units_by_sku: dict[object, int] = {}
    stockout_events_by_sku: dict[object, int] = {}
    records = []
    fulfilled_ids = []

    for order_id in order_index["Order_ID"]:
        group = valid.loc[valid["Order_ID"] == order_id]
        if "Quantity" in group:
            qty = pd.to_numeric(group["Quantity"], errors="coerce").fillna(1.0).clip(lower=0)
            requested = group.assign(_qty=qty).groupby("SKU_ID")["_qty"].sum().to_dict()
        else:
            requested = group.groupby("SKU_ID").size().to_dict()
        requested = {sku: int(math.ceil(float(units))) for sku, units in requested.items() if pd.notna(sku)}
        unallocated = {sku: units for sku, units in requested.items() if sku not in layout_skus}
        short = {
            sku: units - remaining.get(sku, 0)
            for sku, units in requested.items()
            if sku in layout_skus and units > remaining.get(sku, 0)
        }
        short = {sku: units for sku, units in short.items() if units > 0}
        for sku, units in short.items():
            stockout_units_by_sku[sku] = stockout_units_by_sku.get(sku, 0) + units
            stockout_events_by_sku[sku] = stockout_events_by_sku.get(sku, 0) + 1
        if unallocated and short:
            status = "unallocated_sku_and_stockout"
        elif unallocated:
            status = "unallocated_sku"
        elif short:
            status = "stockout"
        else:
            status = "fulfilled"
            for sku, units in requested.items():
                remaining[sku] -= units
            fulfilled_ids.append(order_id)
        records.append({
            "Order_ID": order_id,
            "Timestamp": group["Timestamp"].min(),
            "Fulfillment_Status": status,
            "Requested_Units": int(sum(requested.values())),
            "Stockout_Units": int(sum(short.values())),
            "Unallocated_Units": int(sum(unallocated.values())),
            "Visited_SKUs": "",
            "Distance_m": 0.0,
            "Complete": status == "fulfilled",
        })

    route_columns = ["Order_ID", "Visited_SKUs", "Distance_m", "Complete"]
    if fulfilled_ids:
        fulfilled_lines = valid.loc[valid["Order_ID"].isin(fulfilled_ids)]
        picked_routes = route_orders(
            fulfilled_lines, layout, locations,
            max_orders=len(fulfilled_ids), include_zero_pick_orders=True,
        )
        route_lookup = picked_routes.set_index("Order_ID")
        for record in records:
            if record["Order_ID"] in route_lookup.index and record["Fulfillment_Status"] == "fulfilled":
                route = route_lookup.loc[record["Order_ID"]]
                record["Visited_SKUs"] = route["Visited_SKUs"]
                record["Distance_m"] = float(route["Distance_m"])
                record["Complete"] = bool(route["Complete"])

    routes = pd.DataFrame(records)
    ledger_rows = []
    all_skus = sorted(set(initial) | set(remaining) | set(stockout_units_by_sku), key=str)
    for sku in all_skus:
        start = initial.get(sku, 0)
        left = remaining.get(sku, 0)
        ledger_rows.append({
            "SKU_ID": sku,
            "Starting_Inventory_Units": start,
            "Depleted_Units": start - left,
            "Remaining_Inventory_Units": left,
            "Stockout_Events": stockout_events_by_sku.get(sku, 0),
            "Stockout_Units": stockout_units_by_sku.get(sku, 0),
        })
    ledger = pd.DataFrame(ledger_rows)
    total_orders = len(routes)
    fulfilled = int(routes["Fulfillment_Status"].eq("fulfilled").sum()) if total_orders else 0
    stockout_orders = int(routes["Stockout_Units"].gt(0).sum()) if total_orders else 0
    unallocated_orders = int(routes["Unallocated_Units"].gt(0).sum()) if total_orders else 0
    summary = {
        "test_orders": total_orders,
        "fulfilled_orders": fulfilled,
        "incomplete_orders": total_orders - fulfilled,
        "completion_rate": fulfilled / total_orders if total_orders else 0.0,
        "stockout_orders": stockout_orders,
        "stockout_units": int(routes["Stockout_Units"].sum()) if total_orders else 0,
        "unallocated_orders": unallocated_orders,
        "unallocated_units": int(routes["Unallocated_Units"].sum()) if total_orders else 0,
        "starting_inventory_units": int(sum(initial.values())),
        "depleted_units": int(ledger["Depleted_Units"].sum()) if not ledger.empty else 0,
        "remaining_inventory_units": int(ledger["Remaining_Inventory_Units"].sum()) if not ledger.empty else 0,
        "total_route_distance_m": float(routes["Distance_m"].sum()) if total_orders else 0.0,
        "average_distance_fulfilled_order_m": (
            float(routes.loc[routes["Complete"], "Distance_m"].mean()) if fulfilled else 0.0
        ),
    }
    return routes, ledger, summary
