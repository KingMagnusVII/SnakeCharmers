"""Bounded, lexicographic MILP assortment experiment."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from .demand_analysis import product_dimensional_fit


@dataclass(frozen=True)
class MILPSelectionResult:
    candidates: pd.DataFrame
    training_orders: int
    completable_training_orders: int
    completed_training_orders: int
    candidate_count: int
    optimality_proven: bool
    solver_status: int
    solver_message: str
    runtime_seconds: float
    primary_optimum: int = 0
    stage1_solver_status: int = 0
    stage2_solver_status: int | None = None
    secondary_represented_orders: int | None = None
    secondary_changed_selection: bool = False


def _order_sets(orders: pd.DataFrame) -> list[tuple[object, frozenset]]:
    grouped = orders.loc[orders["Order_ID"].notna() & orders["SKU_ID"].notna()].groupby("Order_ID", sort=True)["SKU_ID"].agg(lambda values: frozenset(values))
    return [(order_id, items) for order_id, items in grouped.items() if items]


def _selected_ids(result, sku_ids: list) -> set:
    if result.x is None:
        return set()
    return {sku_ids[i] for i, value in enumerate(result.x[:len(sku_ids)]) if value > 0.5}


def _stage1_model(sku_ids: list, complete_orders: list[frozenset], max_skus: int):
    n_skus, n_orders = len(sku_ids), len(complete_orders)
    n_vars = n_skus + n_orders
    index = {sku: i for i, sku in enumerate(sku_ids)}
    objective = np.zeros(n_vars)
    objective[n_skus:] = -1.0
    matrix = lil_matrix((sum(map(len, complete_orders)), n_vars), dtype=float)
    row = 0
    for order_i, items in enumerate(complete_orders):
        for sku in items:
            matrix[row, n_skus + order_i] = 1.0
            matrix[row, index[sku]] = -1.0
            row += 1
    cap = lil_matrix((1, n_vars), dtype=float)
    cap[0, :n_skus] = 1.0
    constraints = [LinearConstraint(matrix.tocsr(), -np.inf, 0.0), LinearConstraint(cap.tocsr(), -np.inf, float(max_skus))]
    return objective, constraints


def _stage2_model(sku_ids: list, complete_orders: list[frozenset], represented_orders: list[frozenset], max_skus: int, primary_optimum: int):
    """Maximize distinct represented orders while retaining Stage-1 optimum."""
    n_skus, n_complete, n_represented = len(sku_ids), len(complete_orders), len(represented_orders)
    y_offset, z_offset = n_skus, n_skus + n_complete
    n_vars = z_offset + n_represented
    index = {sku: i for i, sku in enumerate(sku_ids)}
    objective = np.zeros(n_vars)
    objective[z_offset:] = -1.0  # maximize one OR variable per represented order
    rows = sum(map(len, complete_orders)) + n_represented + sum(map(len, represented_orders))
    matrix = lil_matrix((rows, n_vars), dtype=float)
    row = 0
    for order_i, items in enumerate(complete_orders):
        for sku in items:
            matrix[row, y_offset + order_i] = 1.0
            matrix[row, index[sku]] = -1.0
            row += 1
    for order_i, items in enumerate(represented_orders):
        z = z_offset + order_i
        matrix[row, z] = 1.0
        for sku in items:
            matrix[row, index[sku]] = -1.0  # z <= sum(selected SKUs)
        row += 1
        for sku in items:  # z >= each selected SKU, making z an OR
            matrix[row, index[sku]] = 1.0
            matrix[row, z] = -1.0
            row += 1
    cap = lil_matrix((1, n_vars), dtype=float)
    cap[0, :n_skus] = 1.0
    primary = lil_matrix((1, n_vars), dtype=float)
    primary[0, y_offset:y_offset + n_complete] = 1.0
    constraints = [
        LinearConstraint(matrix.tocsr(), -np.inf, 0.0),
        LinearConstraint(cap.tocsr(), -np.inf, float(max_skus)),
        LinearConstraint(primary.tocsr(), float(primary_optimum), np.inf),
    ]
    return objective, constraints


def select_milp_order_coverage_candidates(profile: pd.DataFrame, locations: pd.DataFrame, training_orders: pd.DataFrame, config: dict) -> MILPSelectionResult:
    """Select an assortment using primary completion then distinct-order coverage."""
    started = perf_counter()
    max_skus = max(0, int(config.get("max_active_skus", 200)))
    pool_limit = max(0, int(config.get("milp_candidate_pool", 0)))
    timeout = max(0.0, float(config.get("milp_time_limit_seconds", 60.0)))
    usable = profile.loc[profile["Physical_Metadata_Usable"].fillna(False)].copy()
    fit = product_dimensional_fit(usable, locations, bool(config.get("allow_rotations", True)))
    feasible_ids = set(fit.loc[fit["Fit_Location_Count"] > 0, "SKU_ID"])
    feasible = usable[usable["SKU_ID"].isin(feasible_ids)].copy()
    training_counts = training_orders.groupby("SKU_ID", dropna=True).agg(
        _training_distinct_orders=("Order_ID", "nunique"),
        _training_order_lines=("SKU_ID", "size"),
    )
    feasible = feasible.join(training_counts, on="SKU_ID").fillna({"_training_distinct_orders": 0, "_training_order_lines": 0})
    feasible = feasible.sort_values(["_training_distinct_orders", "_training_order_lines", "SKU_ID"], ascending=[False, False, True], kind="mergesort")
    if pool_limit:
        feasible = feasible.head(pool_limit)
    feasible = feasible.drop(columns=["_training_distinct_orders", "_training_order_lines"])
    pool_ids = set(feasible["SKU_ID"])
    orders = _order_sets(training_orders)
    complete_orders = [items for _, items in orders if items <= pool_ids]
    represented_orders = [items & pool_ids for _, items in orders if items & pool_ids]
    sku_ids = sorted(pool_ids, key=str)
    empty = feasible.iloc[0:0].copy()
    if max_skus == 0 or not sku_ids or not complete_orders:
        return MILPSelectionResult(empty, len(orders), len(complete_orders), 0, len(feasible), True, 0, "No MILP variables required", perf_counter() - started)

    objective, constraints = _stage1_model(sku_ids, complete_orders, max_skus)
    stage1 = milp(objective, integrality=np.ones(len(objective)), bounds=Bounds(0, 1), constraints=constraints, options={"time_limit": timeout, "presolve": True})
    stage1_selected = _selected_ids(stage1, sku_ids)
    primary_value = sum(items <= stage1_selected for items in complete_orders)
    if stage1.status != 0:
        selected = stage1_selected
        candidates = feasible[feasible["SKU_ID"].isin(selected)].sort_values("SKU_ID", kind="mergesort").reset_index(drop=True)
        return MILPSelectionResult(candidates, len(orders), len(complete_orders), primary_value, len(feasible), False, int(stage1.status), f"Stage 1: {stage1.message}; secondary solve skipped", perf_counter() - started, primary_value, int(stage1.status), None, None)

    objective, constraints = _stage2_model(sku_ids, complete_orders, represented_orders, max_skus, primary_value)
    stage2 = milp(objective, integrality=np.ones(len(objective)), bounds=Bounds(0, 1), constraints=constraints, options={"time_limit": timeout, "presolve": True})
    selected = _selected_ids(stage2, sku_ids) if stage2.x is not None else stage1_selected
    completed = sum(items <= selected for items in complete_orders)
    represented = sum(bool(items & selected) for _, items in orders)
    candidates = feasible[feasible["SKU_ID"].isin(selected)].sort_values("SKU_ID", kind="mergesort").reset_index(drop=True)
    return MILPSelectionResult(candidates, len(orders), len(complete_orders), completed, len(feasible), stage2.status == 0, int(stage2.status), f"Stage 1: {stage1.message}; Stage 2: {stage2.message}", perf_counter() - started, primary_value, int(stage1.status), int(stage2.status), represented, selected != stage1_selected)
