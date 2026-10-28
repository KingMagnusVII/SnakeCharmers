import pandas as pd

from src.baseline import select_order_coverage_candidates


def test_order_coverage_selector_prefers_skus_that_complete_more_whole_orders():
    profile = pd.DataFrame([
        {"SKU_ID": sku, "Width_cm": 1, "Height_cm": 1, "Depth_cm": 1,
         "Weight_kg": 1, "Physical_Metadata_Usable": True,
         "Recorded_Order_Lines": lines, "Distinct_Orders": orders,
         "ABC_Class": "A", "Category": "test"}
        for sku, lines, orders in [("a", 2, 2), ("b", 2, 2), ("c", 1, 1)]
    ])
    locations = pd.DataFrame([
        {"Location_ID": f"L{i}", "Bin_Width_cm": 10, "Bin_Height_cm": 10,
         "Bin_Depth_cm": 10, "Volumetric_Capacity_cm3": 1000}
        for i in range(1, 4)
    ])
    orders = pd.DataFrame([
        {"Order_ID": "o1", "SKU_ID": "a"},
        {"Order_ID": "o1", "SKU_ID": "b"},
        {"Order_ID": "o2", "SKU_ID": "a"},
        {"Order_ID": "o2", "SKU_ID": "b"},
        {"Order_ID": "o3", "SKU_ID": "c"},
    ])
    config = {"max_active_skus": 2, "allow_rotations": True}

    selected = select_order_coverage_candidates(profile, locations, orders, config)

    assert set(selected["SKU_ID"]) == {"a", "b"}
