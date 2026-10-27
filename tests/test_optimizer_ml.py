import pandas as pd

from src.optimizer import optimize_layout


CONFIG = {
    "allow_rotations": True,
    "representative_inventory_units": 1,
    "ergonomics": {"heavy_sku_weight_kg": 10, "max_shelf_level_for_heavy_skus": 2},
    "incompatibility_rules": {},
    "objective_weights": {"distance": 1.0, "affinity": 0.0, "ergonomic": 0.1},
}


def _profile():
    """Create two feasible SKUs with different ML demand forecasts."""
    return pd.DataFrame([
        {
            "SKU_ID": "a",
            "Width_cm": 5,
            "Height_cm": 5,
            "Depth_cm": 5,
            "Weight_kg": 1,
            "Inventory_Units": 1,
            "Category": "safe",
            "Hazard_Class": "NONE",
            "Handling_Type": "NORMAL",
            "Volume_cm3": 125,
            "ABC_Class": "A",
            "Physical_Metadata_Usable": True,
            "Predicted_Next_Week_Demand": 100.0,
        },
        {
            "SKU_ID": "b",
            "Width_cm": 5,
            "Height_cm": 5,
            "Depth_cm": 5,
            "Weight_kg": 1,
            "Inventory_Units": 1,
            "Category": "safe",
            "Hazard_Class": "NONE",
            "Handling_Type": "NORMAL",
            "Volume_cm3": 125,
            "ABC_Class": "B",
            "Physical_Metadata_Usable": True,
            "Predicted_Next_Week_Demand": 10.0,
        },
    ])


def _locations():
    """Create a near and far feasible bin so priority changes the result."""
    base = {
        "Rack_ID": "R1",
        "Bay": 1,
        "Shelf_Level": 1,
        "Bin_Width_cm": 10,
        "Bin_Height_cm": 10,
        "Bin_Depth_cm": 10,
        "Volumetric_Capacity_cm3": 1000,
        "Max_Weight_Capacity_kg": 40,
        "Shelf_Max_Load_kg": 100,
        "Rack_Max_Load_kg": 100,
    }
    return pd.DataFrame([
        {**base, "Location_ID": "L1", "X_m": 0.0, "Y_m": 0.0, "Distance_to_Dispatch_Depot_m": 1.0},
        {**base, "Location_ID": "L2", "X_m": 1.0, "Y_m": 0.0, "Distance_to_Dispatch_Depot_m": 10.0},
    ])


def test_optimizer_places_high_forecast_sku_first():
    """The SKU with higher predicted demand should get the best feasible bin."""
    # Historical baseline order intentionally puts the lower-forecast SKU first.
    baseline = pd.DataFrame([
        {"SKU_ID": "b", "Location_ID": "L1"},
        {"SKU_ID": "a", "Location_ID": "L2"},
    ])

    optimized, info = optimize_layout(
        _profile(),
        _locations(),
        baseline,
        pd.DataFrame(),
        CONFIG,
    )

    # ML priority reverses the baseline order, so high-demand SKU 'a' gets L1.
    assert optimized.loc[optimized.SKU_ID == "a", "Location_ID"].iloc[0] == "L1"
    assert optimized.loc[optimized.SKU_ID == "b", "Location_ID"].iloc[0] == "L2"
    assert info["ml_demand_priority_used"] is True
