import pandas as pd

from src.ml_demand import forecast_next_week_demand


CONFIG = {"demand_statuses": ["delivered"]}


def _profile():
    """Create a tiny SKU profile with the fields required by the ML forecaster."""
    return pd.DataFrame([
        {"SKU_ID": "a", "Category": "electronics"},
        {"SKU_ID": "b", "Category": "home"},
    ])


def _orders():
    """Create enough weekly history for the Ridge model to train."""
    rows = []
    # Repeated weekly demand gives the lag/rolling features real history.
    for week in range(20):
        for sku, repeat in (("a", (week % 4) + 1), ("b", 2)):
            for line in range(repeat):
                rows.append({
                    "Order_ID": f"o-{week}-{sku}-{line}",
                    "SKU_ID": sku,
                    "Order_Status": "delivered",
                    "Timestamp": pd.Timestamp("2026-01-05") + pd.Timedelta(weeks=week),
                })
    return pd.DataFrame(rows)


def test_ml_forecast_trains_and_returns_nonnegative_predictions():
    """The ML stage should train on sufficient history and return one forecast per SKU."""
    result, info = forecast_next_week_demand(_orders(), _profile(), CONFIG)

    assert info["trained"] is True
    assert info["model"] == "Ridge"
    assert info["forecast_horizon"] == "next_week"
    assert set(result.SKU_ID) == {"a", "b"}
    assert result["Predicted_Next_Week_Demand"].notna().all()
    assert (result["Predicted_Next_Week_Demand"] >= 0).all()


def test_ml_forecast_gracefully_falls_back_without_valid_history():
    """Missing timestamps should not crash the pipeline or create fake demand."""
    orders = _orders().assign(Timestamp=None)
    result, info = forecast_next_week_demand(orders, _profile(), CONFIG)

    assert info["trained"] is False
    assert info["reason"] == "no_valid_timestamps"
    assert (result["Predicted_Next_Week_Demand"] == 0).all()
