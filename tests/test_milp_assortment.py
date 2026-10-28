import pandas as pd

from src.milp_assortment import select_milp_order_coverage_candidates


def _inputs():
    profile = pd.DataFrame([
        {"SKU_ID": sku, "Width_cm": 1, "Height_cm": 1, "Depth_cm": 1, "Weight_kg": 1,
         "Physical_Metadata_Usable": True, "Recorded_Order_Lines": 1, "Distinct_Orders": 1,
         "ABC_Class": "A"}
        for sku in ["a", "b", "c"]
    ])
    locations = pd.DataFrame([{"Location_ID": f"L{i}", "Bin_Width_cm": 10, "Bin_Height_cm": 10,
                               "Bin_Depth_cm": 10, "Volumetric_Capacity_cm3": 1000} for i in range(3)])
    orders = pd.DataFrame({"Order_ID": ["o1", "o1", "o2", "o2", "o3"],
                          "SKU_ID": ["a", "b", "a", "b", "c"]})
    return profile, locations, orders


def test_milp_maximizes_complete_orders_under_cap():
    profile, locations, orders = _inputs()
    result = select_milp_order_coverage_candidates(profile, locations, orders,
                                                    {"max_active_skus": 2, "milp_time_limit_seconds": 5})
    assert set(result.candidates.SKU_ID) == {"a", "b"}
    assert result.completed_training_orders == 2
    assert result.completable_training_orders == 3
    assert result.candidate_count == 3
    assert result.primary_optimum == result.completed_training_orders == 2
    assert result.stage1_solver_status == 0
    assert result.stage2_solver_status == 0
    assert len(result.candidates) <= 2


def test_secondary_objective_cannot_reduce_proven_primary_optimum():
    profile, locations, orders = _inputs()
    result = select_milp_order_coverage_candidates(
        profile,
        locations,
        orders,
        {"max_active_skus": 2, "milp_time_limit_seconds": 5},
    )
    assert result.optimality_proven is True
    assert result.completed_training_orders == result.primary_optimum


def test_milp_timeout_is_reported_and_secondary_is_not_claimed():
    profile, locations, orders = _inputs()
    result = select_milp_order_coverage_candidates(
        profile,
        locations,
        orders,
        {"max_active_skus": 2, "milp_time_limit_seconds": 0},
    )
    assert result.optimality_proven is False
    assert result.stage1_solver_status != 0
    assert result.stage2_solver_status is None
    assert "secondary solve skipped" in result.solver_message


def test_milp_excludes_orders_with_individually_infeasible_skus():
    profile, locations, orders = _inputs()
    profile.loc[profile.SKU_ID == "c", "Width_cm"] = 100
    result = select_milp_order_coverage_candidates(profile, locations, orders, {"max_active_skus": 2})
    assert result.completable_training_orders == 2
    assert "c" not in set(result.candidates.SKU_ID)


def test_milp_is_deterministic_and_respects_candidate_pool():
    profile, locations, orders = _inputs()
    config = {"max_active_skus": 1, "milp_candidate_pool": 2, "milp_time_limit_seconds": 5}
    first = select_milp_order_coverage_candidates(profile, locations, orders, config)
    second = select_milp_order_coverage_candidates(profile, locations, orders, config)
    assert first.candidates.SKU_ID.tolist() == second.candidates.SKU_ID.tolist()
    assert len(first.candidates) <= config["max_active_skus"]
    assert first.candidate_count == 2
