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
st.subheader("Baseline versus optimized")
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
    # Separate confirmed violations from checks that remain unverified.
    st.subheader("Validation")
    validation = pd.read_csv(DATA / "optimized_violations.csv")
    confirmed = int((validation["Status"] == "VIOLATION").sum()) if "Status" in validation else 0
    unverified = int((validation["Status"] == "UNVERIFIED").sum()) if "Status" in validation else 0
    st.metric("Confirmed violations", confirmed)
    st.metric("Unverified checks", unverified)
    if unverified:
        st.warning(
            "Unverified checks are not proof of compliance. Product hazard, "
            "handling, or stock data may be missing; review the saved validation "
            "reports before treating this layout as operationally safe."
        )

# Show the strongest retained SKU affinity pairs.
st.subheader("Affinity pairs")
st.dataframe(
    pd.read_csv(DATA / "affinity_pairs.csv").head(50),
    use_container_width=True,
)
