"""Machine-learning demand forecasting for warehouse slotting."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def forecast_next_week_demand(
    orders: pd.DataFrame,
    profile: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, dict]:
    """Predict next-week SKU demand with a lightweight supervised ML model.

    The target is weekly recorded order-line count. Lag and rolling-demand
    features make the model temporal, while SKU historical demand and category
    provide product-level context. A Ridge model keeps the stage deterministic
    and inexpensive enough for the hackathon pipeline.
    """
    result = profile.copy()
    result["Predicted_Next_Week_Demand"] = 0.0

    scoped = orders.loc[
        orders["Order_Status"].isin(config.get("demand_statuses", ["delivered"]))
    ].copy()
    scoped["Timestamp"] = pd.to_datetime(scoped["Timestamp"], errors="coerce")
    scoped = scoped.dropna(subset=["Timestamp", "SKU_ID"])
    if scoped.empty:
        return result, {"model": "ridge", "trained": False, "reason": "no_valid_timestamps"}

    # Weekly demand series for every SKU, including zero-demand weeks.
    scoped["Week"] = scoped["Timestamp"].dt.to_period("W").dt.start_time
    weeks = pd.date_range(scoped["Week"].min(), scoped["Week"].max(), freq="7D")
    sku_ids = result["SKU_ID"].dropna().astype(str).unique()
    grid = pd.MultiIndex.from_product([sku_ids, weeks], names=["SKU_ID", "Week"]).to_frame(index=False)
    observed = scoped.assign(SKU_ID=scoped["SKU_ID"].astype(str)).groupby(
        ["SKU_ID", "Week"], as_index=False
    ).size().rename(columns={"size": "Demand"})
    series = grid.merge(observed, on=["SKU_ID", "Week"], how="left")
    series["Demand"] = series["Demand"].fillna(0.0)
    series = series.sort_values(["SKU_ID", "Week"], kind="mergesort")

    grouped = series.groupby("SKU_ID", sort=False)["Demand"]
    series["Lag_1"] = grouped.shift(1)
    series["Lag_4"] = grouped.shift(4)
    series["Rolling_4"] = grouped.transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
    series["Historical_Mean"] = grouped.transform(lambda s: s.shift(1).expanding().mean())
    series["Week_Index"] = (series["Week"] - series["Week"].min()).dt.days / 7.0

    categories = result[["SKU_ID", "Category"]].copy()
    categories["SKU_ID"] = categories["SKU_ID"].astype(str)
    series = series.merge(categories.drop_duplicates("SKU_ID"), on="SKU_ID", how="left")
    series = series.dropna(subset=["Lag_1", "Lag_4", "Rolling_4", "Historical_Mean"])

    # Need enough history to learn a meaningful lag relationship.
    if len(series) < 20:
        return result, {"model": "ridge", "trained": False, "reason": "insufficient_training_rows"}

    features = ["Lag_1", "Lag_4", "Rolling_4", "Historical_Mean", "Week_Index", "Category"]
    numeric = features[:-1]
    categorical = ["Category"]
    preprocessor = ColumnTransformer(
        [
            ("numeric", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]), numeric),
            ("category", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]), categorical),
        ]
    )
    model = Pipeline([
        ("features", preprocessor),
        ("regressor", Ridge(alpha=1.0)),
    ])
    model.fit(series[features], np.log1p(series["Demand"]))

    # Build one feature row representing the next week for every SKU.
    latest = series.sort_values("Week").groupby("SKU_ID", as_index=False).tail(1).copy()
    latest["Week_Index"] = latest["Week_Index"] + 1.0
    predictions = np.expm1(model.predict(latest[features])).clip(0.0)
    prediction_frame = pd.DataFrame({"SKU_ID": latest["SKU_ID"].values, "Predicted_Next_Week_Demand": predictions})
    result["SKU_ID"] = result["SKU_ID"].astype(str)
    result = result.drop(columns=["Predicted_Next_Week_Demand"])
    result = result.merge(prediction_frame, on="SKU_ID", how="left")
    result["Predicted_Next_Week_Demand"] = result["Predicted_Next_Week_Demand"].fillna(0.0)

    info = {
        "model": "Ridge",
        "trained": True,
        "training_rows": int(len(series)),
        "forecast_horizon": "next_week",
        "target": "weekly_recorded_order_lines",
        "features": features,
        "predicted_skus": int(len(prediction_frame)),
    }
    return result, info
