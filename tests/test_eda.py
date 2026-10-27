import ast
from pathlib import Path

import pandas as pd
import pytest

from src.affinity_analysis import compute_affinity
from src.demand_analysis import build_demand_profile, product_dimensional_fit
from scripts.run_eda import _affinity_input_quality


def test_demand_uses_distinct_orders_and_keeps_zero_and_unmatched_skus():
    orders = pd.DataFrame({"Order_ID": ["o1", "o1", "o2", "o3"], "SKU_ID": ["a", "a", "a", "missing"], "Order_Status": ["delivered"] * 4})
    skus = pd.DataFrame({"SKU_ID": ["a", "zero"], "Width_cm": [1, 1], "Height_cm": [1, 1], "Depth_cm": [1, 1], "Weight_kg": [1, 1]})
    profile, quality = build_demand_profile(orders, skus, {"demand_statuses": ["delivered"], "abc_thresholds": {"A": .8, "B": .95}})
    assert profile.loc[profile.SKU_ID.eq("a"), "Distinct_Orders"].item() == 2
    assert profile.loc[profile.SKU_ID.eq("a"), "Recorded_Order_Lines"].item() == 3
    assert profile.loc[profile.SKU_ID.eq("zero"), "ABC_Class"].item() == "ZERO"
    assert quality["unmatched_observed_skus"] == 1


def test_demand_reports_duplicate_sku_master_records_and_keeps_first_record():
    orders = pd.DataFrame(
        {"Order_ID": ["o1"], "SKU_ID": ["a"], "Order_Status": ["delivered"]}
    )
    skus = pd.DataFrame(
        {
            "SKU_ID": ["a", "a"],
            "Width_cm": [1, 2],
            "Height_cm": [1, 2],
            "Depth_cm": [1, 2],
            "Weight_kg": [1, 2],
        }
    )

    profile, quality = build_demand_profile(
        orders,
        skus,
        {"demand_statuses": ["delivered"], "abc_thresholds": {"A": 0.8, "B": 0.95}},
    )

    assert quality["duplicate_sku_master_records"] == 1
    assert profile.loc[profile.SKU_ID.eq("a"), "Width_cm"].item() == 1


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


def test_affinity_input_quality_counts_missing_identifiers_without_double_counting():
    scoped = pd.DataFrame(
        {
            "Order_ID": ["o1", "o2", None, "o3", None],
            "SKU_ID": ["a", "b", "c", None, None],
        }
    )

    quality = _affinity_input_quality(scoped)

    assert quality == {
        "input_rows": 5,
        "rows_missing_order_id": 2,
        "rows_missing_sku_id": 2,
        "rows_missing_both_identifiers": 1,
        "excluded_rows_missing_identifiers": 3,
        "retained_rows": 2,
    }
    assert quality["retained_rows"] + quality["excluded_rows_missing_identifiers"] == quality["input_rows"]


def test_pipeline_does_not_overwrite_eda_affinity_artifact():
    pipeline_source = (
        Path(__file__).resolve().parents[1] / "scripts" / "run_pipeline.py"
    ).read_text(encoding="utf-8")
    pipeline_tree = ast.parse(pipeline_source)

    writes_eda_affinity = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "to_csv"
        and any(
            isinstance(argument, ast.Constant)
            and argument.value == "affinity_pairs.csv"
            for argument in node.args
        )
        for node in ast.walk(pipeline_tree)
    )

    assert "affinity = compute_affinity(scoped, active)" in pipeline_source
    assert not writes_eda_affinity


def test_dimensional_fit_honors_rotations_invalid_metadata_and_no_fit():
    skus = pd.DataFrame({"SKU_ID": ["rotates", "no-fit", "unknown"], "Width_cm": [30, 50, None], "Height_cm": [40, 1, 1], "Depth_cm": [20, 1, 1], "Weight_kg": [1, 1, 1]})
    locations = pd.DataFrame({"Bin_Width_cm": [40], "Bin_Height_cm": [30], "Bin_Depth_cm": [20], "Volumetric_Capacity_cm3": [24000]})
    fit = product_dimensional_fit(skus, locations, allow_rotations=True).set_index("SKU_ID")
    assert fit.loc["rotates", "Fit_Location_Count"] == 1
    assert fit.loc["no-fit", "Fits_No_Location"]
    assert not fit.loc["unknown", "Fit_Determinable"]
