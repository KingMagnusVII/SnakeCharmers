import pandas as pd

from src.affinity_analysis import compute_affinity
from src.baseline import allocate_baseline
from src.evaluation import compare, evaluate
from src.feasibility import fits_product, validate_layout
from src.optimizer import optimize_layout
from src.warehouse_generator import generate_warehouse
from scripts.run_pipeline import _validation_summary


CONFIG = {
    "allow_rotations": True,
    "representative_inventory_units": 1,
    "ergonomics": {"heavy_sku_weight_kg": 10, "max_shelf_level_for_heavy_skus": 2},
    "incompatibility_rules": {
        "category_hazard_pairs": [{"category": "food", "hazard_class": "OXIDIZER"}],
        "hazard_handling_pairs": [{"hazard_class": "FLAMMABLE", "handling_type": "HEAT"}],
    },
}


def _locations():
    return pd.DataFrame([
        {"Location_ID": "L1", "Rack_ID": "R1", "Bay": 1, "Shelf_Level": 1, "Bin_Width_cm": 10, "Bin_Height_cm": 10, "Bin_Depth_cm": 10, "Volumetric_Capacity_cm3": 1000, "Max_Weight_Capacity_kg": 40, "Shelf_Max_Load_kg": 50, "Rack_Max_Load_kg": 50, "Distance_to_Dispatch_Depot_m": 2},
        {"Location_ID": "L2", "Rack_ID": "R1", "Bay": 1, "Shelf_Level": 1, "Bin_Width_cm": 10, "Bin_Height_cm": 10, "Bin_Depth_cm": 100, "Volumetric_Capacity_cm3": 1000, "Max_Weight_Capacity_kg": 40, "Shelf_Max_Load_kg": 50, "Rack_Max_Load_kg": 50, "Distance_to_Dispatch_Depot_m": 4},
        {"Location_ID": "L3", "Rack_ID": "R1", "Bay": 2, "Shelf_Level": 3, "Bin_Width_cm": 10, "Bin_Height_cm": 10, "Bin_Depth_cm": 10, "Volumetric_Capacity_cm3": 1000, "Max_Weight_Capacity_kg": 40, "Shelf_Max_Load_kg": 50, "Rack_Max_Load_kg": 50, "Distance_to_Dispatch_Depot_m": 6},
    ])


def _skus():
    return pd.DataFrame([
        {"SKU_ID": "a", "Width_cm": 10, "Height_cm": 10, "Depth_cm": 10, "Weight_kg": 30, "Inventory_Units": 1, "Category": "safe", "Hazard_Class": "NONE", "Handling_Type": "NORMAL", "Volume_cm3": 1000, "Recorded_Order_Lines": 3, "Physical_Metadata_Usable": True, "ABC_Class": "A"},
        {"SKU_ID": "b", "Width_cm": 5, "Height_cm": 5, "Depth_cm": 5, "Weight_kg": 30, "Inventory_Units": 1, "Category": "safe", "Hazard_Class": "NONE", "Handling_Type": "NORMAL", "Volume_cm3": 125, "Recorded_Order_Lines": 2, "Physical_Metadata_Usable": True, "ABC_Class": "B"},
    ])


def _rules(layout, skus=None, locations=None, config=CONFIG):
    return set(validate_layout(layout, _skus() if skus is None else skus, _locations() if locations is None else locations, config).Rule)


def test_warehouse_deterministic_count():
    assert len(generate_warehouse()) == 244
    assert generate_warehouse().equals(generate_warehouse())


def test_rotation_boundary_and_missing_dimensions():
    location = pd.Series({"Bin_Width_cm": 40, "Bin_Height_cm": 30, "Bin_Depth_cm": 20})
    product = pd.Series({"Width_cm": 30, "Height_cm": 40, "Depth_cm": 20})
    assert fits_product(product, location, True)
    assert not fits_product(product, location, False)
    assert fits_product(pd.Series({"Width_cm": 40, "Height_cm": 30, "Depth_cm": 20}), location)
    assert not fits_product(pd.Series({"Width_cm": None, "Height_cm": 1, "Depth_cm": 1}), location)


def test_missing_bin_dimension_is_unverified_but_nonpositive_is_violation():
    skus = _skus()
    layout = pd.DataFrame([{"SKU_ID": "b", "Location_ID": "L1"}])
    locations = _locations()
    locations.loc[0, "Bin_Depth_cm"] = None
    missing_result = validate_layout(layout, skus, locations, CONFIG)
    assert "missing_bin_dimension" in set(missing_result.loc[missing_result.Status == "UNVERIFIED", "Rule"])
    assert "dimensional_fit" not in set(missing_result.loc[missing_result.Status == "VIOLATION", "Rule"])

    locations.loc[0, "Bin_Depth_cm"] = 0
    invalid_result = validate_layout(layout, skus, locations, CONFIG)
    assert "invalid_bin_dimension" in set(invalid_result.loc[invalid_result.Status == "VIOLATION", "Rule"])


def test_affinity_deduplicates_basket():
    orders = pd.DataFrame({"Order_ID": ["o1", "o1", "o1", "o2"], "SKU_ID": ["a", "a", "b", "a"]})
    assert compute_affinity(orders).iloc[0].Pair_Count == 1


def test_duplicate_assignments_and_unknown_references_are_violations():
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}, {"SKU_ID": "a", "Location_ID": "L1"}, {"SKU_ID": "missing", "Location_ID": "missing-location"}])
    rules = _rules(layout)
    assert {"assignment_uniqueness", "location_uniqueness", "sku_reference", "location_reference"} <= rules


def test_missing_invalid_data_and_capacity_violations_are_reported():
    skus = _skus()
    skus.loc[0, ["Width_cm", "Weight_kg"]] = [0, -1]
    skus.loc[1, ["Width_cm", "Height_cm", "Depth_cm", "Inventory_Units"]] = [10, 10, 10, 2]
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}, {"SKU_ID": "b", "Location_ID": "L2"}])
    rules = _rules(layout, skus)
    assert {"invalid_physical_dimension", "invalid_weight_kg", "bin_volume_capacity", "location_weight_capacity"} <= rules


def test_missing_physical_data_is_unverified_not_compliant():
    skus = _skus()
    skus.loc[0, ["Width_cm", "Weight_kg"]] = [None, None]
    result = validate_layout(pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}]), skus, _locations(), CONFIG)
    unknown = set(result.loc[result.Status == "UNVERIFIED", "Rule"])
    assert {"missing_physical_dimension", "missing_weight_kg"} <= unknown


def test_invalid_representative_inventory_fallback_is_a_violation():
    skus = _skus()
    skus.loc[0, "Inventory_Units"] = None
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])

    # Invalid fallback values must be rejected because they cannot represent stock safely.
    for fallback in (0, -1, "not-a-number", None):
        config = {**CONFIG, "representative_inventory_units": fallback}
        result = validate_layout(layout, skus, _locations(), config)
        invalid = result[result.Rule == "invalid_representative_inventory_units"]
        assert len(invalid) == 1
        assert invalid.iloc[0].Status == "VIOLATION"

    # A valid fallback is used only when observed inventory is missing.
    valid_config = {**CONFIG, "representative_inventory_units": 1}
    valid_result = validate_layout(layout, skus, _locations(), valid_config)
    assumed = valid_result[valid_result.Rule == "inventory_units"]
    assert len(assumed) == 1
    assert assumed.iloc[0].Status == "UNVERIFIED"
    assert not (valid_result.Status == "VIOLATION").any()


def test_aggregate_shelf_and_rack_overload_and_ergonomics_are_reported():
    overloaded = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}, {"SKU_ID": "b", "Location_ID": "L2"}])
    assert {"aggregate_shelf_load", "aggregate_rack_load"} <= _rules(overloaded)
    assert "ergonomic_shelf_height" in _rules(pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L3"}]))


def test_known_incompatibilities_and_unknown_attributes_are_distinct():
    skus = _skus()
    skus.loc[0, ["Category", "Hazard_Class", "Handling_Type"]] = ["food", "OXIDIZER", "HEAT"]
    skus.loc[1, ["Hazard_Class", "Handling_Type"]] = ["UNSPECIFIED", "UNSPECIFIED"]
    result = validate_layout(pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}, {"SKU_ID": "b", "Location_ID": "L2"}]), skus, _locations(), CONFIG)
    assert "configured_incompatibility" in set(result.Rule)
    assert set(result.loc[result.Status == "UNVERIFIED", "Rule"]) >= {"hazard_class", "handling_type"}


def test_empty_and_schema_invalid_allocations():
    assert validate_layout(pd.DataFrame(), _skus(), _locations(), CONFIG).empty
    assert "layout_schema" in _rules(pd.DataFrame({"SKU_ID": ["a"]}))


def test_baseline_and_optimizer_use_the_same_known_constraint_checks():
    profile = _skus().copy()
    locations = _locations()
    locations[["Shelf_Max_Load_kg", "Rack_Max_Load_kg"]] = 100
    baseline, excluded = allocate_baseline(profile, locations, CONFIG)
    optimized, _ = optimize_layout(profile, locations, baseline, pd.DataFrame(), CONFIG)
    assert excluded.empty
    for layout in (baseline, optimized):
        result = validate_layout(layout, profile, locations, CONFIG)
        assert not (result.Status == "VIOLATION").any()


def test_optimizer_uses_affinity_to_prefer_nearby_related_skus():
    profile = _skus().copy()
    locations = pd.DataFrame([
        {"Location_ID": "L1", "Rack_ID": "R1", "Bay": 1, "Shelf_Level": 1, "X_m": 0.0, "Y_m": 0.0, "Bin_Width_cm": 10, "Bin_Height_cm": 10, "Bin_Depth_cm": 10, "Volumetric_Capacity_cm3": 1000, "Max_Weight_Capacity_kg": 40, "Shelf_Max_Load_kg": 100, "Rack_Max_Load_kg": 100, "Distance_to_Dispatch_Depot_m": 1.0},
        {"Location_ID": "L2", "Rack_ID": "R1", "Bay": 2, "Shelf_Level": 1, "X_m": 1.0, "Y_m": 0.0, "Bin_Width_cm": 10, "Bin_Height_cm": 10, "Bin_Depth_cm": 10, "Volumetric_Capacity_cm3": 1000, "Max_Weight_Capacity_kg": 40, "Shelf_Max_Load_kg": 100, "Rack_Max_Load_kg": 100, "Distance_to_Dispatch_Depot_m": 10.0},
        {"Location_ID": "L3", "Rack_ID": "R1", "Bay": 3, "Shelf_Level": 1, "X_m": 100.0, "Y_m": 0.0, "Bin_Width_cm": 10, "Bin_Height_cm": 10, "Bin_Depth_cm": 100, "Volumetric_Capacity_cm3": 1000, "Max_Weight_Capacity_kg": 40, "Shelf_Max_Load_kg": 100, "Rack_Max_Load_kg": 100, "Distance_to_Dispatch_Depot_m": 2.0},
    ])
    baseline = pd.DataFrame([
        {"SKU_ID": "a", "Location_ID": "L1"},
        {"SKU_ID": "b", "Location_ID": "L3"},
    ])
    affinity = pd.DataFrame([{"SKU_A": "a", "SKU_B": "b", "Pair_Count": 10, "Lift": 4.0}])

    # Compare the distance-only choice with a stronger affinity objective.
    without_affinity, _ = optimize_layout(profile, locations, baseline, pd.DataFrame(), CONFIG)
    affinity_config = {**CONFIG, "objective_weights": {"distance": 1.0, "affinity": 1.0, "ergonomic": 0.1}}
    with_affinity, _ = optimize_layout(profile, locations, baseline, affinity, affinity_config)

    assert without_affinity.loc[without_affinity.SKU_ID == "b", "Location_ID"].iloc[0] == "L3"
    assert with_affinity.loc[with_affinity.SKU_ID == "b", "Location_ID"].iloc[0] == "L2"


def test_baseline_reports_products_that_fit_no_bin_dimensions():
    # The product has usable metadata but is too large for every test bin.
    profile = _skus().iloc[[0]].copy()
    profile.loc[profile.index[0], ["Width_cm", "Height_cm", "Depth_cm"]] = [50, 50, 50]
    _, excluded = allocate_baseline(
        profile,
        _locations(),
        {**CONFIG, "max_active_skus": 10},
    )
    assert len(excluded) == 1
    assert excluded.iloc[0]["Reason"] == "does_not_fit_any_bin_dimensions"


def test_evaluation_arithmetic_zero_distance_and_incomplete_orders():
    profile, locations = _skus(), _locations()
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])
    routes = pd.DataFrame({"Distance_m": [0.0, 10.0], "Complete": [True, "false"]})
    metrics = evaluate(
        routes,
        layout,
        profile,
        locations,
        {
            "walking_speed_m_per_min": 10,
            "pick_handling_seconds": 0,
            "max_active_skus": 1,
        },
    )
    assert metrics["orders_simulated"] == 2
    assert metrics["complete_orders"] == 1
    assert metrics["total_distance_m"] == 10
    assert metrics["average_distance_m"] == 5
    assert metrics["allocation_coverage"] == 0.5
    assert metrics["active_assortment_sku_count"] == 1
    assert metrics["active_assortment_allocated_sku_count"] == 1
    assert metrics["active_assortment_unallocated_sku_count"] == 0
    assert metrics["active_assortment_coverage"] == 1.0
    assert metrics["order_line_coverage"] == 0.6
    empty_metrics = evaluate(pd.DataFrame(columns=["Distance_m", "Complete"]), layout, profile, locations, {})
    assert empty_metrics["average_distance_m"] == 0.0
    comparison = compare({"total_distance_m": 10.0}, {"total_distance_m": 7.5})
    assert comparison.iloc[0].Change == -2.5


def test_oversized_storage_fits_and_allocates_four_outlier_skus():
    locations = generate_warehouse()
    oversized = locations[locations.Location_Type == "OVERSIZED"]
    assert len(locations) == 244
    assert set(oversized.Location_ID) == {
        "OVR-AUTO-01", "OVR-AUTO-02", "OVR-AUTO-03", "OVR-LONG-01"
    }

    # Three wide automotive products and one long stationery product match
    # the real outlier dimensions found in the active assortment.
    profile = pd.DataFrame([
        {"SKU_ID": "auto-67", "Width_cm": 67, "Height_cm": 10, "Depth_cm": 67, "Weight_kg": 4.105, "Inventory_Units": 1, "Category": "automotivo", "Hazard_Class": "NONE", "Handling_Type": "NORMAL", "Volume_cm3": 44890, "Recorded_Order_Lines": 4, "Physical_Metadata_Usable": True, "ABC_Class": "A"},
        {"SKU_ID": "auto-65", "Width_cm": 65, "Height_cm": 11, "Depth_cm": 65, "Weight_kg": 5.950, "Inventory_Units": 1, "Category": "automotivo", "Hazard_Class": "NONE", "Handling_Type": "NORMAL", "Volume_cm3": 46475, "Recorded_Order_Lines": 3, "Physical_Metadata_Usable": True, "ABC_Class": "A"},
        {"SKU_ID": "auto-61", "Width_cm": 61, "Height_cm": 14, "Depth_cm": 61, "Weight_kg": 7.625, "Inventory_Units": 1, "Category": "automotivo", "Hazard_Class": "NONE", "Handling_Type": "NORMAL", "Volume_cm3": 52094, "Recorded_Order_Lines": 2, "Physical_Metadata_Usable": True, "ABC_Class": "B"},
        {"SKU_ID": "long-101", "Width_cm": 15, "Height_cm": 15, "Depth_cm": 101, "Weight_kg": 0.750, "Inventory_Units": 1, "Category": "papelaria", "Hazard_Class": "NONE", "Handling_Type": "NORMAL", "Volume_cm3": 22725, "Recorded_Order_Lines": 1, "Physical_Metadata_Usable": True, "ABC_Class": "C"},
    ])
    baseline, excluded = allocate_baseline(
        profile, locations, {**CONFIG, "max_active_skus": 4}
    )
    assert excluded.empty
    assert len(baseline) == 4
    assert set(baseline.Location_ID).issubset(set(oversized.Location_ID))
    validation = validate_layout(baseline, profile, locations, CONFIG)
    assert not (validation.Status == "VIOLATION").any()


def test_validation_summary_separates_violations_from_unverified_checks():
    results = pd.DataFrame({"Status": ["VIOLATION", "UNVERIFIED", "UNVERIFIED"]})
    assert _validation_summary(results) == {"known_violations": 1, "unverified_checks": 2}
    assert _validation_summary(pd.DataFrame(columns=["Status"])) == {
        "known_violations": 0,
        "unverified_checks": 0,
    }


def test_evaluation_exposes_missing_safety_and_inventory_attributes():
    profile = _skus()
    profile.loc[profile.SKU_ID == "a", ["Hazard_Class", "Handling_Type", "Inventory_Units"]] = ["UNSPECIFIED", "UNKNOWN", None]
    locations = _locations()
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])
    metrics = evaluate(pd.DataFrame(columns=["Distance_m", "Complete"]), layout, profile, locations, CONFIG)
    assert metrics["unknown_hazard_attributes"] == 1
    assert metrics["unknown_handling_attributes"] == 1
    assert metrics["unknown_inventory_attributes"] == 1


def test_zero_inventory_is_not_reported_as_invalid_stock():
    skus = _skus()
    skus.loc[skus.SKU_ID == "a", "Inventory_Units"] = 0
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])
    result = validate_layout(layout, skus, _locations(), CONFIG)
    assert "invalid_inventory_units" not in set(result.Rule)
    assert "bin_volume_capacity" not in set(result.loc[result.Status == "VIOLATION", "Rule"])
    assert "location_weight_capacity" not in set(result.loc[result.Status == "VIOLATION", "Rule"])


def test_evaluation_utilization_multiplies_volume_by_inventory_units():
    profile = _skus().iloc[[0]].copy()
    profile.loc[profile.index[0], "Inventory_Units"] = 3
    locations = _locations().copy()
    locations["Volumetric_Capacity_cm3"] = 4000
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])
    metrics = evaluate(
        pd.DataFrame(columns=["Distance_m", "Complete"]),
        layout,
        profile,
        locations,
        {"representative_inventory_units": 1, "max_active_skus": 1},
    )
    assert metrics["whole_warehouse_utilization"] == 0.25
    assert metrics["allocated_bin_utilization"] == 0.75


def test_baseline_does_not_overload_aggregate_rack_capacity():
    profile = _skus().copy()
    locations = _locations().copy()
    locations["Rack_Max_Load_kg"] = 50
    baseline, excluded = allocate_baseline(profile, locations, {**CONFIG, "max_active_skus": 2})
    assert len(baseline) == 1
    assert len(excluded) == 1
    assert excluded.iloc[0]["Reason"] == "no_remaining_feasible_location"
    validation = validate_layout(baseline, profile, locations, CONFIG)
    assert "aggregate_rack_load" not in set(validation.loc[validation.Status == "VIOLATION", "Rule"])
