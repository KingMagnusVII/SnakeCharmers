import pandas as pd

from src.feasibility import fits_product
from src.warehouse_generator import generate_warehouse


def test_warehouse_keeps_four_oversized_slots_with_specialized_dimensions():
    warehouse = generate_warehouse()
    oversized = warehouse.loc[warehouse["Location_Type"] == "OVERSIZED"]

    assert len(oversized) == 4
    assert set(oversized["Location_ID"]) == {
        "OVR-AUTO-01",
        "OVR-AUTO-02",
        "OVR-AUTO-03",
        "OVR-LONG-01",
    }


def test_bulky_product_fits_a_configured_oversized_slot():
    product = pd.Series(
        {"SKU_ID": "bulky-example", "Width_cm": 118, "Height_cm": 93, "Depth_cm": 23}
    )
    oversized = generate_warehouse().query("Location_Type == 'OVERSIZED'")

    assert any(fits_product(product, location, allow_rotations=True)
               for _, location in oversized.iterrows())


def test_long_product_fits_a_configured_long_item_slot():
    product = pd.Series(
        {"SKU_ID": "long-example", "Width_cm": 70, "Height_cm": 3, "Depth_cm": 105}
    )
    long_slot = generate_warehouse().set_index("Location_ID").loc["OVR-LONG-01"]

    assert fits_product(product, long_slot, allow_rotations=True)
