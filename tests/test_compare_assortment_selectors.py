import pandas as pd
import pytest

from scripts.compare_assortment_selectors import calculate_metrics, compare_selector_sets, completed_order_ids, sample_training_orders


def test_selector_set_comparison_handles_identical_and_disjoint_sets():
    identical = compare_selector_sets({"a", "b"}, {"a", "b"})
    assert identical["shared_count"] == 2
    assert identical["left_only_count"] == identical["right_only_count"] == 0
    assert identical["jaccard"] == 1.0
    disjoint = compare_selector_sets({"a"}, {"b"})
    assert disjoint["shared_count"] == 0
    assert disjoint["jaccard"] == 0.0


def test_completed_order_comparison_counts_shared_and_unique_orders():
    orders = pd.DataFrame({"Order_ID": ["o1", "o1", "o2", "o2", "o3"], "SKU_ID": ["a", "b", "a", "c", "d"]})
    greedy = completed_order_ids(pd.DataFrame({"SKU_ID": ["a", "b"]}), orders)
    milp = completed_order_ids(pd.DataFrame({"SKU_ID": ["a", "b", "d"]}), orders)
    comparison = compare_selector_sets(greedy, milp)
    assert comparison["shared_count"] == 1
    assert comparison["left_only_count"] == 0
    assert comparison["right_only_count"] == 1


def test_metrics_separate_evaluable_orders_from_pool_exclusions():
    orders = pd.DataFrame({"Order_ID": ["o1", "o1", "o2", "o3"], "SKU_ID": ["a", "b", "a", "z"]})
    pool = pd.DataFrame({"SKU_ID": ["a", "b"]})
    selected = pd.DataFrame({"SKU_ID": ["a", "b"]})
    metrics = calculate_metrics("test", selected, orders, pool, 0.25)
    assert metrics["training_orders_evaluated"] == 3
    assert metrics["training_orders_evaluable_in_pool"] == 2
    assert metrics["training_orders_excluded_outside_pool"] == 1
    assert metrics["complete_training_orders"] == 2
    assert metrics["complete_pct_of_all_training"] == pytest.approx(66.66666666666666)
    assert metrics["candidate_pool_coverage_pct"] == pytest.approx(66.66666666666666)
    assert metrics["complete_pct_of_evaluable"] == 100.0


def test_metrics_reports_selection_size_validation_failure():
    orders = pd.DataFrame({"Order_ID": ["o1"], "SKU_ID": ["a"]})
    pool = pd.DataFrame({"SKU_ID": ["a", "b", "c"]})
    selected = pool.copy()
    metrics = calculate_metrics("test", selected, orders, pool, 0.0, max_assortment_size=2)
    assert metrics["selection_size_valid"] is False
    assert metrics["validation_failure"] == "selected 3 > limit 2"


def test_training_sample_is_deterministic_and_whole_order_based():
    orders = pd.DataFrame({"Order_ID": ["late", "early", "early", "middle"], "SKU_ID": ["d", "a", "b", "c"], "Timestamp": pd.to_datetime(["2020-01-03", "2020-01-01", "2020-01-01", "2020-01-02"])})
    sampled = sample_training_orders(orders, 2)
    assert sampled.Order_ID.unique().tolist() == ["early", "middle"]
    assert len(sampled) == 3
