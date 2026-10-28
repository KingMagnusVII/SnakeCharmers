import pandas as pd

from src.inventory_simulation import (
    chronological_train_test_split,
    estimate_starting_inventory,
    simulate_inventory_picking,
)


def test_chronological_split_keeps_test_timestamps_after_training():
    orders = pd.DataFrame({
        "Order_ID": ["a", "a", "b", "c", "d"],
        "SKU_ID": ["x", "y", "x", "y", "x"],
        "Timestamp": pd.to_datetime([
            "2020-01-01", "2020-01-01", "2020-01-02",
            "2020-01-03", "2020-01-04",
        ]),
        "Order_Status": ["delivered"] * 5,
    })

    train, test, cutoff = chronological_train_test_split(orders, train_fraction=0.5)

    assert set(train.Order_ID) == {"a", "b"}
    assert set(test.Order_ID) == {"c", "d"}
    assert train.Timestamp.max() < cutoff
    assert test.Timestamp.min() >= cutoff


def test_14_day_inventory_estimate_uses_only_training_line_rate():
    training = pd.DataFrame({
        "Order_ID": ["a", "b"],
        "SKU_ID": ["sku-a", "sku-a"],
        "Timestamp": pd.to_datetime(["2020-01-01", "2020-01-02"]),
        "Quantity": [1.0, 1.0],
    })

    estimates, training_days = estimate_starting_inventory(training, coverage_days=14)

    assert training_days == 2
    row = estimates.set_index("SKU_ID").loc["sku-a"]
    assert row.Training_Order_Lines == 2
    assert row.Estimated_Daily_Demand == 1
    assert row.Starting_Inventory_Units == 14


def test_stock_depletion_stockouts_and_unallocated_skus_are_tracked():
    training = pd.DataFrame({
        "Order_ID": ["a", "b"],
        "SKU_ID": ["sku-a", "sku-a"],
        "Timestamp": pd.to_datetime(["2020-01-01", "2020-01-02"]),
        "Quantity": [1.0, 1.0],
    })
    estimates, _ = estimate_starting_inventory(training, coverage_days=14)

    full_order_lines = pd.DataFrame({
        "Order_ID": ["o-full"] * 14,
        "SKU_ID": ["sku-a"] * 14,
        "Timestamp": pd.to_datetime(["2020-01-04"] * 14),
        "Quantity": [1.0] * 14,
    })
    test_orders = pd.concat([
        pd.DataFrame({
            "Order_ID": ["o-fail", "o-fail"],
            "SKU_ID": ["sku-a", "not-stocked"],
            "Timestamp": pd.to_datetime(["2020-01-03", "2020-01-03"]),
            "Quantity": [1.0, 1.0],
        }),
        full_order_lines,
        pd.DataFrame({
            "Order_ID": ["o-stockout"],
            "SKU_ID": ["sku-a"],
            "Timestamp": pd.to_datetime(["2020-01-05"]),
            "Quantity": [1.0],
        }),
    ], ignore_index=True)
    layout = pd.DataFrame([{"SKU_ID": "sku-a", "Location_ID": "L1"}])
    locations = pd.DataFrame([{"Location_ID": "L1", "X_m": 3.0, "Y_m": 2.0}])

    routes, ledger, summary = simulate_inventory_picking(
        test_orders, layout, locations, estimates
    )

    statuses = routes.set_index("Order_ID").Fulfillment_Status.to_dict()
    assert statuses == {
        "o-fail": "unallocated_sku",
        "o-full": "fulfilled",
        "o-stockout": "stockout",
    }
    assert summary["test_orders"] == 3
    assert summary["fulfilled_orders"] == 1
    assert summary["stockout_orders"] == 1
    assert summary["stockout_units"] == 1
    assert summary["unallocated_orders"] == 1
    assert summary["depleted_units"] == 14
    assert summary["remaining_inventory_units"] == 0
    row = ledger.set_index("SKU_ID").loc["sku-a"]
    assert row.Starting_Inventory_Units == 14
    assert row.Depleted_Units == 14
    assert row.Stockout_Events == 1


def test_baseline_and_optimized_replay_same_orders_and_inventory():
    estimates = pd.DataFrame({
        "SKU_ID": ["sku-a"],
        "Starting_Inventory_Units": [2],
    })
    test_orders = pd.DataFrame({
        "Order_ID": ["o1", "o2", "o3"],
        "SKU_ID": ["sku-a", "sku-a", "sku-a"],
        "Timestamp": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
        "Quantity": [1.0, 1.0, 1.0],
    })
    baseline = pd.DataFrame([{"SKU_ID": "sku-a", "Location_ID": "L1"}])
    optimized = pd.DataFrame([{"SKU_ID": "sku-a", "Location_ID": "L2"}])
    locations = pd.DataFrame([
        {"Location_ID": "L1", "X_m": 3.0, "Y_m": 2.0},
        {"Location_ID": "L2", "X_m": 6.0, "Y_m": 2.0},
    ])

    base_routes, base_ledger, base_metrics = simulate_inventory_picking(
        test_orders, baseline, locations, estimates
    )
    opt_routes, opt_ledger, opt_metrics = simulate_inventory_picking(
        test_orders, optimized, locations, estimates
    )

    assert base_routes.Order_ID.tolist() == opt_routes.Order_ID.tolist()
    assert base_metrics["stockout_orders"] == opt_metrics["stockout_orders"] == 1
    assert base_metrics["depleted_units"] == opt_metrics["depleted_units"] == 2
    assert base_ledger.Remaining_Inventory_Units.sum() == opt_ledger.Remaining_Inventory_Units.sum()
    assert base_metrics["total_route_distance_m"] != opt_metrics["total_route_distance_m"]
