import pandas as pd

from src.affinity_analysis import compute_affinity
from src.baseline import allocate_baseline
from src.evaluation import compare, evaluate
from src.feasibility import fits_product, validate_layout
from src.optimizer import improve_layout_by_route_distance, optimize_layout
from src.routing import route_orders
from src.warehouse_generator import generate_warehouse


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
    assert len(generate_warehouse()) == 240
    assert generate_warehouse().equals(generate_warehouse())


def test_rotation_boundary_and_missing_dimensions():
    location = pd.Series({"Bin_Width_cm": 40, "Bin_Height_cm": 30, "Bin_Depth_cm": 20})
    product = pd.Series({"Width_cm": 30, "Height_cm": 40, "Depth_cm": 20})
    assert fits_product(product, location, True)
    assert not fits_product(product, location, False)
    assert fits_product(pd.Series({"Width_cm": 40, "Height_cm": 30, "Depth_cm": 20}), location)
    assert not fits_product(pd.Series({"Width_cm": None, "Height_cm": 1, "Depth_cm": 1}), location)


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


def test_evaluation_arithmetic_zero_distance_and_incomplete_orders():
    profile, locations = _skus(), _locations()
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])
    routes = pd.DataFrame({"Distance_m": [0.0, 10.0], "Complete": [True, "false"]})
    metrics = evaluate(routes, layout, profile, locations, {"walking_speed_m_per_min": 10, "pick_handling_seconds": 0})
    assert metrics["orders_simulated"] == 2
    assert metrics["complete_orders"] == 1
    assert metrics["incomplete_orders"] == 1
    assert metrics["completion_rate"] == 0.5
    assert metrics["total_distance_m"] == 10
    assert metrics["average_distance_m"] == 5
    assert metrics["average_distance_complete_orders_m"] == 0
    assert metrics["allocation_coverage"] == 0.5
    assert metrics["order_line_coverage"] == 0.6
    empty_metrics = evaluate(pd.DataFrame(columns=["Distance_m", "Complete"]), layout, profile, locations, {})
    assert empty_metrics["orders_simulated"] == 0
    assert empty_metrics["complete_orders"] == 0
    assert empty_metrics["incomplete_orders"] == 0
    assert empty_metrics["completion_rate"] == 0.0
    assert empty_metrics["average_distance_m"] == 0.0
    assert empty_metrics["average_distance_complete_orders_m"] == 0.0
    comparison = compare({"total_distance_m": 10.0}, {"total_distance_m": 7.5})
    assert comparison.iloc[0].Change == -2.5


def test_evaluation_all_incomplete_orders_use_zero_completed_average():
    profile, locations = _skus(), _locations()
    layout = pd.DataFrame(columns=["SKU_ID", "Location_ID"])
    routes = pd.DataFrame(
        {"Distance_m": [0.0, 0.0], "Complete": [False, "false"]}
    )

    metrics = evaluate(routes, layout, profile, locations, {})

    assert metrics["complete_orders"] == 0
    assert metrics["incomplete_orders"] == 2
    assert metrics["completion_rate"] == 0.0
    assert metrics["average_distance_complete_orders_m"] == 0.0


def test_evaluation_preserves_existing_metric_keys():
    profile, locations = _skus(), _locations()
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])
    routes = pd.DataFrame({"Distance_m": [4.0], "Complete": [True]})

    metrics = evaluate(routes, layout, profile, locations, {})

    assert {
        "orders_simulated",
        "complete_orders",
        "total_distance_m",
        "average_distance_m",
        "estimated_time_min",
        "whole_warehouse_utilization",
        "allocated_bin_utilization",
        "allocation_coverage",
        "order_line_coverage",
        "unknown_hazard_attributes",
    } <= metrics.keys()


def _route_locations():
    return pd.DataFrame(
        [
            {"Location_ID": "L1", "X_m": 2.0, "Y_m": 0.0},
            {"Location_ID": "L2", "X_m": 0.0, "Y_m": 3.0},
        ]
    )


def test_route_records_order_with_every_sku_unallocated():
    orders = pd.DataFrame({"Order_ID": ["o1"], "SKU_ID": ["missing"]})
    layout = pd.DataFrame(columns=["SKU_ID", "Location_ID"])

    routes = route_orders(orders, layout, _route_locations())

    assert routes.to_dict("records") == [
        {
            "Order_ID": "o1",
            "Visited_SKUs": "",
            "Distance_m": 0.0,
            "Complete": False,
        }
    ]


def test_route_sample_limit_counts_unassigned_source_orders():
    orders = pd.DataFrame(
        {
            "Order_ID": ["o1", "o2", "o3"],
            "SKU_ID": ["missing", "a", "b"],
        }
    )
    layout = pd.DataFrame(
        [{"SKU_ID": "a", "Location_ID": "L1"}, {"SKU_ID": "b", "Location_ID": "L2"}]
    )

    routes = route_orders(orders, layout, _route_locations(), max_orders=2)

    assert routes.Order_ID.tolist() == ["o1", "o2"]
    assert routes.Complete.tolist() == [False, True]


def test_route_marks_mixed_assigned_and_unassigned_order_incomplete():
    orders = pd.DataFrame(
        {"Order_ID": ["o1", "o1"], "SKU_ID": ["a", "missing"]}
    )
    layout = pd.DataFrame([{"SKU_ID": "a", "Location_ID": "L1"}])

    routes = route_orders(orders, layout, _route_locations())

    assert routes.loc[0, "Visited_SKUs"] == "a"
    assert routes.loc[0, "Distance_m"] == 4.0
    assert not routes.loc[0, "Complete"]


def test_route_empty_input_and_layout_keep_route_schema():
    orders = pd.DataFrame(columns=["Order_ID", "SKU_ID"])
    layout = pd.DataFrame(columns=["SKU_ID", "Location_ID"])

    routes = route_orders(orders, layout, _route_locations())

    assert routes.empty
    assert routes.columns.tolist() == [
        "Order_ID",
        "Visited_SKUs",
        "Distance_m",
        "Complete",
    ]


def _optimizer_objective_locations():
    return pd.DataFrame(
        [
            {
                "Location_ID": "L1",
                "Rack_ID": "R1",
                "Bay": 1,
                "Shelf_Level": 1,
                "Bin_Width_cm": 20,
                "Bin_Height_cm": 20,
                "Bin_Depth_cm": 20,
                "Volumetric_Capacity_cm3": 8000,
                "Max_Weight_Capacity_kg": 40,
                "Shelf_Max_Load_kg": 100,
                "Rack_Max_Load_kg": 100,
                "Distance_to_Dispatch_Depot_m": 10,
                "X_m": 10,
                "Y_m": 0,
            },
            {
                "Location_ID": "L2",
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
                "Distance_to_Dispatch_Depot_m": 11,
                "X_m": 11,
                "Y_m": 0,
            },
            {
                "Location_ID": "L3",
                "Rack_ID": "R1",
                "Bay": 2,
                "Shelf_Level": 1,
                "Bin_Width_cm": 10,
                "Bin_Height_cm": 10,
                "Bin_Depth_cm": 10,
                "Volumetric_Capacity_cm3": 1000,
                "Max_Weight_Capacity_kg": 40,
                "Shelf_Max_Load_kg": 100,
                "Rack_Max_Load_kg": 100,
                "Distance_to_Dispatch_Depot_m": 1,
                "X_m": 1,
                "Y_m": 0,
            },
        ]
    )


def _optimizer_objective_profile():
    return pd.DataFrame(
        [
            {
                "SKU_ID": "A",
                "Width_cm": 20,
                "Height_cm": 20,
                "Depth_cm": 20,
                "Weight_kg": 1,
                "Inventory_Units": 1,
                "Category": "safe",
                "Hazard_Class": "NONE",
                "Handling_Type": "NORMAL",
                "Volume_cm3": 8000,
                "Recorded_Order_Lines": 2,
                "Physical_Metadata_Usable": True,
                "ABC_Class": "A",
            },
            {
                "SKU_ID": "B",
                "Width_cm": 5,
                "Height_cm": 5,
                "Depth_cm": 5,
                "Weight_kg": 1,
                "Inventory_Units": 1,
                "Category": "safe",
                "Hazard_Class": "NONE",
                "Handling_Type": "NORMAL",
                "Volume_cm3": 125,
                "Recorded_Order_Lines": 1,
                "Physical_Metadata_Usable": True,
                "ABC_Class": "B",
            },
        ]
    )


def _optimizer_objective_config(affinity_weight, distance_weight=1.0):
    return {
        "allow_rotations": True,
        "representative_inventory_units": 1,
        "ergonomics": {
            "heavy_sku_weight_kg": 10,
            "max_shelf_level_for_heavy_skus": 2,
        },
        "incompatibility_rules": {},
        "objective_weights": {
            "distance": distance_weight,
            "affinity": affinity_weight,
            "ergonomic": 0.0,
            "waste": 0.0,
        },
    }


def _optimizer_objective_affinity():
    return pd.DataFrame(
        {
            "SKU_A": ["A"],
            "SKU_B": ["B"],
            "Pair_Count": [100],
        }
    )


def _optimized_location(layout, sku):
    return layout.loc[layout.SKU_ID.eq(sku), "Location_ID"].item()


def test_optimizer_affinity_weight_changes_placement():
    profile = _optimizer_objective_profile()
    locations = _optimizer_objective_locations()
    baseline = pd.DataFrame(
        [
            {"SKU_ID": "A", "Location_ID": "L1"},
            {"SKU_ID": "B", "Location_ID": "L3"},
        ]
    )
    affinity = _optimizer_objective_affinity()

    no_affinity, _ = optimize_layout(
        profile,
        locations,
        baseline,
        affinity,
        _optimizer_objective_config(0.0),
    )
    with_affinity, _ = optimize_layout(
        profile,
        locations,
        baseline,
        affinity,
        _optimizer_objective_config(2.0),
    )

    assert _optimized_location(no_affinity, "B") == "L3"
    assert _optimized_location(with_affinity, "B") == "L2"


def test_optimizer_zero_affinity_weight_removes_affinity_influence():
    profile = _optimizer_objective_profile()
    locations = _optimizer_objective_locations()
    baseline = pd.DataFrame(
        [
            {"SKU_ID": "A", "Location_ID": "L1"},
            {"SKU_ID": "B", "Location_ID": "L3"},
        ]
    )

    layout, info = optimize_layout(
        profile,
        locations,
        baseline,
        _optimizer_objective_affinity(),
        _optimizer_objective_config(0.0),
    )

    assert _optimized_location(layout, "B") == "L3"
    assert info["objective_weights"]["affinity"] == 0.0


def test_optimizer_configured_distance_weight_changes_scoring():
    profile = _optimizer_objective_profile()
    locations = _optimizer_objective_locations()
    baseline = pd.DataFrame(
        [
            {"SKU_ID": "A", "Location_ID": "L1"},
            {"SKU_ID": "B", "Location_ID": "L3"},
        ]
    )

    distance_weighted, _ = optimize_layout(
        profile,
        locations,
        baseline,
        pd.DataFrame(),
        _optimizer_objective_config(0.0, distance_weight=1.0),
    )
    tie_broken, _ = optimize_layout(
        profile,
        locations,
        baseline,
        pd.DataFrame(),
        _optimizer_objective_config(0.0, distance_weight=0.0),
    )

    assert _optimized_location(distance_weighted, "B") == "L3"
    assert _optimized_location(tie_broken, "B") == "L2"


def test_optimizer_empty_or_missing_affinity_is_safe_and_deterministic():
    profile = _optimizer_objective_profile()
    locations = _optimizer_objective_locations()
    baseline = pd.DataFrame(
        [
            {"SKU_ID": "A", "Location_ID": "L1"},
            {"SKU_ID": "B", "Location_ID": "L3"},
        ]
    )
    config = _optimizer_objective_config(2.0)

    first, first_info = optimize_layout(profile, locations, baseline, None, config)
    second, second_info = optimize_layout(profile, locations, baseline, None, config)

    pd.testing.assert_frame_equal(first, second)
    assert first_info == second_info
    assert _optimized_location(first, "B") == "L3"


def _local_search_locations():
    return pd.DataFrame(
        [
            {
                "Location_ID": "L1",
                "Rack_ID": "R1",
                "Bay": 1,
                "Shelf_Level": 1,
                "Bin_Width_cm": 20,
                "Bin_Height_cm": 20,
                "Bin_Depth_cm": 20,
                "Volumetric_Capacity_cm3": 8000,
                "Max_Weight_Capacity_kg": 40,
                "Shelf_Max_Load_kg": 100,
                "Rack_Max_Load_kg": 100,
                "Distance_to_Dispatch_Depot_m": 10,
                "X_m": 10,
                "Y_m": 0,
            },
            {
                "Location_ID": "L2",
                "Rack_ID": "R1",
                "Bay": 2,
                "Shelf_Level": 1,
                "Bin_Width_cm": 20,
                "Bin_Height_cm": 20,
                "Bin_Depth_cm": 20,
                "Volumetric_Capacity_cm3": 8000,
                "Max_Weight_Capacity_kg": 40,
                "Shelf_Max_Load_kg": 100,
                "Rack_Max_Load_kg": 100,
                "Distance_to_Dispatch_Depot_m": 1,
                "X_m": 1,
                "Y_m": 0,
            },
        ]
    )


def _local_search_profile():
    return pd.DataFrame(
        [
            {
                "SKU_ID": "A",
                "Width_cm": 5,
                "Height_cm": 5,
                "Depth_cm": 5,
                "Weight_kg": 1,
                "Inventory_Units": 1,
                "Category": "safe",
                "Hazard_Class": "NONE",
                "Handling_Type": "NORMAL",
                "Volume_cm3": 125,
                "Recorded_Order_Lines": 3,
                "Physical_Metadata_Usable": True,
                "ABC_Class": "A",
            },
            {
                "SKU_ID": "B",
                "Width_cm": 5,
                "Height_cm": 5,
                "Depth_cm": 5,
                "Weight_kg": 1,
                "Inventory_Units": 1,
                "Category": "safe",
                "Hazard_Class": "NONE",
                "Handling_Type": "NORMAL",
                "Volume_cm3": 125,
                "Recorded_Order_Lines": 1,
                "Physical_Metadata_Usable": True,
                "ABC_Class": "B",
            },
        ]
    )


def _local_search_config():
    return {
        "allow_rotations": True,
        "representative_inventory_units": 1,
        "ergonomics": {
            "heavy_sku_weight_kg": 10,
            "max_shelf_level_for_heavy_skus": 2,
        },
        "incompatibility_rules": {},
    }


def _local_search_orders():
    return pd.DataFrame(
        {
            "Order_ID": ["o1", "o2", "o3", "o4"],
            "SKU_ID": ["A", "A", "A", "B"],
        }
    )


def test_local_search_accepts_known_improving_swap():
    layout = pd.DataFrame(
        [{"SKU_ID": "A", "Location_ID": "L1"}, {"SKU_ID": "B", "Location_ID": "L2"}]
    )

    improved, info = improve_layout_by_route_distance(
        _local_search_profile(),
        _local_search_locations(),
        layout,
        _local_search_orders(),
        _local_search_config(),
        max_swap_attempts=1,
    )

    assert improved.set_index("SKU_ID").loc["A", "Location_ID"] == "L2"
    assert info["accepted_swaps"] == 1
    assert info["final_distance_m"] < info["starting_distance_m"]


def test_local_search_rejects_route_distance_regression():
    layout = pd.DataFrame(
        [{"SKU_ID": "A", "Location_ID": "L2"}, {"SKU_ID": "B", "Location_ID": "L1"}]
    )

    result, info = improve_layout_by_route_distance(
        _local_search_profile(),
        _local_search_locations(),
        layout,
        _local_search_orders(),
        _local_search_config(),
        max_swap_attempts=1,
    )

    pd.testing.assert_frame_equal(result, layout)
    assert info["accepted_swaps"] == 0
    assert info["final_distance_m"] == info["starting_distance_m"]


def test_local_search_rejects_infeasible_swap_and_preserves_assignments():
    profile = _local_search_profile()
    profile.loc[profile.SKU_ID == "A", ["Width_cm", "Height_cm", "Depth_cm"]] = 20
    locations = _local_search_locations()
    locations.loc[locations.Location_ID == "L2", ["Bin_Width_cm", "Bin_Height_cm", "Bin_Depth_cm"]] = 10
    layout = pd.DataFrame(
        [{"SKU_ID": "A", "Location_ID": "L1"}, {"SKU_ID": "B", "Location_ID": "L2"}]
    )

    result, info = improve_layout_by_route_distance(
        profile,
        locations,
        layout,
        _local_search_orders(),
        _local_search_config(),
        max_swap_attempts=1,
    )

    pd.testing.assert_frame_equal(result, layout)
    assert set(result.SKU_ID) == set(layout.SKU_ID)
    assert result.Location_ID.is_unique
    assert info["accepted_swaps"] == 0


def test_local_search_is_deterministic_and_obeys_attempt_limit():
    layout = pd.DataFrame(
        [{"SKU_ID": "A", "Location_ID": "L1"}, {"SKU_ID": "B", "Location_ID": "L2"}]
    )
    kwargs = {
        "profile": _local_search_profile(),
        "locations": _local_search_locations(),
        "layout": layout,
        "orders": _local_search_orders(),
        "config": _local_search_config(),
        "max_swap_attempts": 0,
    }

    first, first_info = improve_layout_by_route_distance(**kwargs)
    second, second_info = improve_layout_by_route_distance(**kwargs)

    pd.testing.assert_frame_equal(first, second)
    assert first_info == second_info
    assert first_info["attempted_swaps"] == 0
    assert first_info["search_terminated_by_limit"]
