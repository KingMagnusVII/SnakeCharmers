"""Streamlit dashboard backed only by generated pipeline artifacts."""

from pathlib import Path  # Handles filesystem paths safely across platforms.

import pandas as pd  # Loads generated CSV artifacts.
import streamlit as st  # Builds the interactive dashboard.

# Resolve the repository root from this dashboard file.
ROOT = Path(__file__).resolve().parent

# Generated pipeline outputs live in data/processed.
DATA = ROOT / "data" / "processed"

# Configure the browser page and use the full dashboard width.
st.set_page_config(page_title="Smart Warehouse Slotting", layout="wide")

# Display the dashboard title.
st.title("Smart Warehouse Slotting & Optimization")

# The comparison file proves that the pipeline has generated evaluation outputs.
comparison = DATA / "evaluation_comparison.csv"

# Stop early with an actionable message when the pipeline has not been run.
if not comparison.exists():
    st.error(
        "Run `python scripts/run_pipeline.py` first; generated outputs are missing."
    )
    st.stop()

# Load and display baseline-versus-optimized metrics.
metrics = pd.read_csv(comparison)
st.caption(
    "Synthetic warehouse geometry and representative-stock assumptions are "
    "simulation inputs, not measured safety data."
)

# Make the headline completion result explicit while keeping the broader source
# sample visible so the conditional 100% is never mistaken for universal coverage.
scope_path = ROOT / "reports" / "order_completion_scope.json"
if scope_path.exists():
    import json

    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    eligible_rate = float(scope.get("eligible_completion_rate", 0.0))
    source_optimized = scope.get("source_first_500_optimized", {})
    source_rate = float(source_optimized.get("completion_rate", 0.0))
    eligible_count = int(scope.get("eligible_orders_evaluated", 0))
    source_count = int(source_optimized.get("orders_simulated", 0))
    st.subheader("Order completion")
    first, second = st.columns(2)
    first.metric(
        "Eligible-order completion",
        f"{eligible_rate:.1%}",
        help=f"{eligible_count} orders whose every SKU is allocated. This is a conditional cohort, not all source orders.",
    )
    second.metric(
        "First 500 source orders",
        f"{source_rate:.1%}",
        help=f"{int(source_optimized.get('complete_orders', 0))}/{source_count} complete, including orders with unallocated SKUs.",
    )
    st.caption(
        "The eligible cohort can reach 100% because orders containing unallocated SKUs are excluded. "
        "Use the first-500 source-order metric to judge overall coverage."
    )

st.subheader("Baseline versus optimized")
if "Baseline" in metrics and "Optimized" in metrics:
    percent_rows = metrics["Metric"].astype(str).eq("completion_rate")
    for column in ("Baseline", "Optimized", "Change"):
        if column in metrics:
            metrics[column] = pd.to_numeric(metrics[column], errors="coerce")
    st.dataframe(
        metrics.style.format(
            {column: "{:.1%}" for column in ("Baseline", "Optimized", "Change") if column in metrics},
            subset=metrics.index[percent_rows],
        ),
        use_container_width=True,
    )
else:
    st.dataframe(metrics, use_container_width=True)

# Split the next section into two dashboard columns.
left, right = st.columns(2)

with left:
    # Show a sample of the optimized SKU-to-location allocation.
    st.subheader("Optimized allocation")
    st.dataframe(
        pd.read_csv(DATA / "optimized_allocation.csv").head(100),
        use_container_width=True,
    )

with right:
    # Show the number of known validation violations in the optimized layout.
    st.subheader("Validation")
    st.metric(
        "Optimized violations",
        len(pd.read_csv(DATA / "optimized_violations.csv")),
    )

# Show the strongest retained SKU affinity pairs.
st.subheader("Affinity pairs")
st.dataframe(
    pd.read_csv(DATA / "affinity_pairs.csv").head(50),
    use_container_width=True,
)
