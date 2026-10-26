"""Reusable demand, Pareto, and dimensional-fit calculations for EDA."""
from __future__ import annotations

from itertools import permutations

import pandas as pd


def select_demand_scope(orders: pd.DataFrame, statuses: list[str]) -> pd.DataFrame:
    """Return demand lines included by status; timestamp quality is measured separately."""
    return orders.loc[orders["Order_Status"].isin(statuses)].copy()


def _physical_metadata(skus: pd.DataFrame) -> pd.DataFrame:
    result = skus.copy()
    dimensions = ["Width_cm", "Height_cm", "Depth_cm"]
    for field in dimensions + ["Weight_kg"]:
        result[field] = pd.to_numeric(result[field], errors="coerce")
    result["Dimensions_Valid"] = result[dimensions].notna().all(axis=1) & (result[dimensions] > 0).all(axis=1)
    result["Weight_Valid"] = result["Weight_kg"].notna() & (result["Weight_kg"] > 0)
    result["Physical_Metadata_Usable"] = result["Dimensions_Valid"] & result["Weight_Valid"]
    result["Volume_cm3"] = result["Width_cm"] * result["Height_cm"] * result["Depth_cm"]
    result.loc[~result["Dimensions_Valid"], "Volume_cm3"] = float("nan")
    return result


def build_demand_profile(orders: pd.DataFrame, skus: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """Build an all-SKU profile whose Pareto denominator is SKU-order incidences."""
    scoped = select_demand_scope(orders, config.get("demand_statuses", ["delivered"]))
    master = _physical_metadata(skus).drop_duplicates("SKU_ID", keep="first")
    observed = scoped.loc[scoped["SKU_ID"].notna()].groupby("SKU_ID", as_index=False).agg(
        Distinct_Orders=("Order_ID", "nunique"), Recorded_Order_Lines=("SKU_ID", "size"))
    universe = pd.Index(master["SKU_ID"].dropna()).union(pd.Index(observed["SKU_ID"])).sort_values()
    profile = pd.DataFrame({"SKU_ID": universe}).merge(observed, on="SKU_ID", how="left")
    profile[["Distinct_Orders", "Recorded_Order_Lines"]] = profile[["Distinct_Orders", "Recorded_Order_Lines"]].fillna(0).astype("int64")
    profile = profile.merge(master, on="SKU_ID", how="left", indicator="Product_Metadata_Match")
    profile["Observed_Demand"] = profile["Distinct_Orders"] > 0
    denominator = int(profile["Distinct_Orders"].sum())
    profile["Demand_Share"] = 0.0
    if denominator:
        profile.loc[profile["Observed_Demand"], "Demand_Share"] = profile.loc[profile["Observed_Demand"], "Distinct_Orders"] / denominator
    profile = profile.sort_values(["Distinct_Orders", "SKU_ID"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    profile["Cumulative_Demand_Share"] = profile["Demand_Share"].cumsum()
    thresholds = config.get("abc_thresholds", {"A": 0.80, "B": 0.95})
    def classify(row: pd.Series) -> str:
        if not row.Observed_Demand:
            return "ZERO"
        return "A" if row.Cumulative_Demand_Share <= thresholds["A"] else "B" if row.Cumulative_Demand_Share <= thresholds["B"] else "C"
    profile["ABC_Class"] = profile.apply(classify, axis=1)
    profile["Demand_Metric"] = "distinct_orders_containing_sku"
    return profile, {"input_order_lines": int(len(orders)), "scoped_order_lines": int(len(scoped)), "scoped_distinct_orders": int(scoped["Order_ID"].nunique()), "sku_order_incidence_denominator": denominator, "positive_demand_skus": int(profile["Observed_Demand"].sum()), "zero_demand_skus": int((~profile["Observed_Demand"]).sum()), "unmatched_observed_skus": int(((profile["Product_Metadata_Match"] == "left_only") & profile["Observed_Demand"]).sum()), "products_missing_or_invalid_dimensions": int((~master["Dimensions_Valid"]).sum()), "products_missing_or_invalid_weight": int((~master["Weight_Valid"]).sum())}


def analyze_demand(orders: pd.DataFrame, skus: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    return build_demand_profile(orders, skus, config)


def product_dimensional_fit(skus: pd.DataFrame, locations: pd.DataFrame, allow_rotations: bool = True) -> pd.DataFrame:
    """Determine fit per SKU using orientation-aware dimensions, never volume alone."""
    master = _physical_metadata(skus).drop_duplicates("SKU_ID", keep="first")
    bin_fields = ["Bin_Width_cm", "Bin_Height_cm", "Bin_Depth_cm"]
    bins = locations.copy()
    for field in bin_fields:
        bins[field] = pd.to_numeric(bins[field], errors="coerce")
    valid_bins = bins[bin_fields].notna().all(axis=1) & (bins[bin_fields] > 0).all(axis=1)
    # Consolidate repeated bin classes (the configured topology currently has one).
    bin_classes = bins.loc[valid_bins, bin_fields + ["Volumetric_Capacity_cm3"]].value_counts().reset_index(name="Location_Count")
    rows = []
    for product in master.itertuples(index=False):
        row = {"SKU_ID": product.SKU_ID, "Dimensions_Valid": bool(product.Dimensions_Valid), "Volume_cm3": product.Volume_cm3}
        if not product.Dimensions_Valid:
            row.update({"Fit_Location_Count": 0, "Fit_Determinable": False, "Fits_No_Location": False, "Small_Fit_Count": False, "Min_Fitting_Volume_Ratio": float("nan")})
        else:
            dims = (product.Width_cm, product.Height_cm, product.Depth_cm)
            orientations = set(permutations(dims)) if allow_rotations else {dims}
            fitting = []
            for bin_class in bin_classes.itertuples(index=False):
                bin_dims = (bin_class.Bin_Width_cm, bin_class.Bin_Height_cm, bin_class.Bin_Depth_cm)
                if any(all(a <= b for a, b in zip(orientation, bin_dims)) for orientation in orientations):
                    fitting.append(bin_class)
            count = int(sum(item.Location_Count for item in fitting))
            ratios = [product.Volume_cm3 / item.Volumetric_Capacity_cm3 for item in fitting if pd.notna(item.Volumetric_Capacity_cm3) and item.Volumetric_Capacity_cm3 > 0]
            row.update({"Fit_Location_Count": count, "Fit_Determinable": True, "Fits_No_Location": count == 0, "Small_Fit_Count": 0 < count <= 5, "Min_Fitting_Volume_Ratio": float(min(ratios)) if ratios else float("nan")})
        rows.append(row)
    return pd.DataFrame(rows).sort_values("SKU_ID", kind="mergesort").reset_index(drop=True)
