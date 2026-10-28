import pandas as pd

from src.routing import route_orders


def _inputs():
    orders = pd.DataFrame(
        {
            "Order_ID": ["001", "002", "003", "003"],
            "SKU_ID": ["MISSING", "A", "A", "MISSING"],
        }
    )
    layout = pd.DataFrame({"SKU_ID": ["A"], "Location_ID": ["BIN-1"]})
    locations = pd.DataFrame(
        {"Location_ID": ["BIN-1"], "X_m": [1.0], "Y_m": [2.0]}
    )
    return orders, layout, locations


def test_route_orders_preserves_historical_pickable_order_sample():
    orders, layout, locations = _inputs()

    routes = route_orders(orders, layout, locations, max_orders=1, include_zero_pick_orders=False)

    assert routes["Order_ID"].tolist() == ["002"]
    assert routes["Complete"].tolist() == [True]


def test_route_orders_can_count_zero_pick_source_orders_separately():
    orders, layout, locations = _inputs()

    routes = route_orders(
        orders, layout, locations, max_orders=2, include_zero_pick_orders=True
    )

    assert routes["Order_ID"].tolist() == ["001", "002"]
    assert routes["Complete"].tolist() == [False, True]
    assert routes["Visited_SKUs"].tolist() == ["", "A"]
