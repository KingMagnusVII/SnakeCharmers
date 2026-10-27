import pandas as pd
import pytest

from src.affinity_analysis import compute_affinity
from src.demand_analysis import build_demand_profile, product_dimensional_fit


def test_demand_uses_distinct_orders_and_keeps_zero_and_unmatched_skus():
    orders = pd.DataFrame({"Order_ID": ["o1", "o1", "o2", "o3"], "SKU_ID": ["a", "a", "a", "missing"], "Order_Status": ["delivered"] * 4})
    skus = pd.DataFrame({"SKU_ID": ["a", "zero"], "Width_cm": [1, 1], "Height_cm": [1, 1], "Depth_cm": [1, 1], "Weight_kg": [1, 1]})
    profile, quality = build_demand_profile(orders, skus, {"demand_statuses": ["delivered"], "abc_thresholds": {"A": .8, "B": .95}})
    assert profile.loc[profile.SKU_ID.eq("a"), "Distinct_Orders"].item() == 2
    assert profile.loc[profile.SKU_ID.eq("a"), "Recorded_Order_Lines"].item() == 3
    assert profile.loc[profile.SKU_ID.eq("zero"), "ABC_Class"].item() == "ZERO"
    assert quality["unmatched_observed_skus"] == 1


def test_abc_boundary_and_deterministic_tie_breaking():
    orders = pd.DataFrame({"Order_ID": ["1", "2", "3", "4", "5"], "SKU_ID": ["b", "a", "a", "b", "c"], "Order_Status": ["delivered"] * 5})
    skus = pd.DataFrame({"SKU_ID": ["a", "b", "c"], "Width_cm": [1] * 3, "Height_cm": [1] * 3, "Depth_cm": [1] * 3, "Weight_kg": [1] * 3})
    profile, _ = build_demand_profile(orders, skus, {"abc_thresholds": {"A": .8, "B": .95}})
    assert profile.SKU_ID.tolist() == ["a", "b", "c"]
    assert profile.loc[0, "ABC_Class"] == "A"  # cumulative 2/5 is through 80%
    assert profile.loc[2, "ABC_Class"] == "C"  # cumulative 100% exceeds B threshold


def test_affinity_metrics_filtering_deduplication_and_empty_input():
    orders = pd.DataFrame({"Order_ID": ["1", "1", "1", "2", "2", "3"], "SKU_ID": ["a", "a", "b", "a", "b", "b"]})
    result = compute_affinity(orders)
    row = result.iloc[0]
    assert (row.SKU_A, row.SKU_B, row.Pair_Count) == ("a", "b", 2)
    assert row.Support == pytest.approx(2 / 3)
    assert row.Confidence_A_to_B == pytest.approx(1)
    assert row.Confidence_B_to_A == pytest.approx(2 / 3)
    assert row.Lift == pytest.approx(1)
    assert compute_affinity(orders, min_pair_count=3).empty
    assert compute_affinity(pd.DataFrame(columns=["Order_ID", "SKU_ID"])).empty


def test_dimensional_fit_honors_rotations_invalid_metadata_and_no_fit():
    skus = pd.DataFrame({"SKU_ID": ["rotates", "no-fit", "unknown"], "Width_cm": [30, 50, None], "Height_cm": [40, 1, 1], "Depth_cm": [20, 1, 1], "Weight_kg": [1, 1, 1]})
    locations = pd.DataFrame({"Bin_Width_cm": [40], "Bin_Height_cm": [30], "Bin_Depth_cm": [20], "Volumetric_Capacity_cm3": [24000]})
    fit = product_dimensional_fit(skus, locations, allow_rotations=True).set_index("SKU_ID")
    assert fit.loc["rotates", "Fit_Location_Count"] == 1
    assert fit.loc["no-fit", "Fits_No_Location"]
    assert not fit.loc["unknown", "Fit_Determinable"]
