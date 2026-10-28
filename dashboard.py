"""Interactive dashboard for Smart Warehouse Slotting & Optimization."""

import datetime
import random
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ============================================================
# CONFIGURATION & HYPER-TECHNICAL THEME
# ============================================================

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed"

st.set_page_config(
    page_title="Warehouse Intelligence Terminal // ROOT",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

THEMES = {
    "CYBER TERMINAL": {
        "background": "#050505",
        "panel": "#0a0a0a",
        "text": "#00ff41",
        "accent": "#00ffff",
        "secondary": "#333333",
        "purple": "#bd93f9",
        "highlight": "#f1fa8c",
        "success": "#00ff41",
        "danger": "#ff003c",
    },
    "DARK MATTER": {
        "background": "#0b0f19",
        "panel": "#111827",
        "text": "#e2e8f0",
        "accent": "#38bdf8",
        "secondary": "#334155",
        "purple": "#a78bfa",
        "highlight": "#facc15",
        "success": "#34d399",
        "danger": "#f43f5e",
    },
}

if "session_id" not in st.session_state:
    st.session_state.session_id = f"0x{random.randint(100000, 999999):06X}"

with st.sidebar:
    st.markdown(
        f"<div style='font-family:monospace; font-size:.7rem;'>USER_AUTH: ROOT // SESSION: {st.session_state.session_id}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("### ⚙️ SYSTEM PREFS")
    selected_theme = st.selectbox("INTERFACE THEME [SELECT]", list(THEMES.keys()))

theme = THEMES[selected_theme]

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@500;600;700&display=swap');
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
        font-family:'Rajdhani',sans-serif;
        background-color:{theme['background']}; color:{theme['text']};
        background-image:linear-gradient({theme['secondary']}90 1px,transparent 1px),linear-gradient(90deg,{theme['secondary']}90 1px,transparent 1px);
        background-size:30px 30px;
    }}
    .stApp {{ background:transparent; }}
    .block-container {{ max-width:1750px; padding-top:1rem; padding-bottom:3rem; }}
    [data-testid="stSidebar"] {{ background:{theme['panel']}; border-right:1px solid {theme['accent']}; }}
    h1,h2,h3,h4,h5,h6 {{ font-family:'Rajdhani',sans-serif !important; color:{theme['text']} !important; text-transform:uppercase; letter-spacing:2px; }}
    [data-testid="stMetric"] {{ background:{theme['panel']}; border:1px solid {theme['secondary']}; border-top:3px solid {theme['accent']}; padding:1rem; }}
    [data-testid="stMetricValue"] {{ color:{theme['accent']} !important; font-family:'Share Tech Mono',monospace !important; }}
    .stButton > button,.stDownloadButton > button {{ border-radius:0; border:1px solid {theme['accent']}; background:transparent; color:{theme['accent']}; font-family:'Share Tech Mono',monospace; text-transform:uppercase; }}
    .stButton > button:hover,.stDownloadButton > button:hover {{ background:{theme['accent']}; color:#000; }}
    .hero {{ padding:2rem; margin:.2rem 0 1.6rem; border:1px solid {theme['accent']}; border-left:8px solid {theme['accent']}; background:{theme['panel']}; }}
    .telemetry-ribbon {{ display:flex; gap:20px; padding:12px 20px; background:{theme['panel']}; border:1px solid {theme['accent']}; font-family:monospace; margin-bottom:25px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# DATA HELPERS
# ============================================================

@st.cache_data
def load_csv(filename):
    path = DATA / filename
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def find_column(df, *keywords):
    if df is None or df.empty:
        return None
    columns = list(df.columns)
    normalized = {str(c).lower().replace(" ", "_"): c for c in columns}
    for keyword in keywords:
        key = keyword.lower().replace(" ", "_")
        if key in normalized:
            return normalized[key]
    for keyword in keywords:
        key = keyword.lower().replace(" ", "_")
        for normalized_name, original_name in normalized.items():
            if key in normalized_name:
                return original_name
    return None


def number_metric(metrics, name, column="Optimized"):
    if metrics is None or metrics.empty:
        return None
    metric_col = find_column(metrics, "Metric")
    value_col = find_column(metrics, column)
    if not metric_col or not value_col:
        return None
    matches = metrics[metrics[metric_col].astype(str).str.lower() == name.lower()]
    if matches.empty:
        return None
    try:
        return float(matches.iloc[0][value_col])
    except (ValueError, TypeError):
        return None


def display_number(value, suffix=""):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.2f}{suffix}"


def plot_3d_category_values(df, category_col, value_col, title, max_points=80):
    if df is None or df.empty or category_col not in df.columns or value_col not in df.columns:
        st.info("[!] INSUFFICIENT DATASTREAM FOR 3D RENDER.")
        return
    plot_df = df[[category_col, value_col]].copy()
    plot_df[value_col] = pd.to_numeric(plot_df[value_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[value_col]).head(max_points)
    if plot_df.empty:
        return
    plot_df[category_col] = plot_df[category_col].astype(str)
    plot_df["_x"] = range(len(plot_df))
    fig = go.Figure()
    for row in plot_df.itertuples(index=False, name=None):
        fig.add_trace(go.Scatter3d(x=[row[2], row[2]], y=[0, 0], z=[0, row[1]], mode="lines", showlegend=False))
    fig.add_trace(go.Scatter3d(x=plot_df["_x"], y=[0] * len(plot_df), z=plot_df[value_col], mode="markers+text", text=plot_df[category_col], name=value_col))
    fig.update_layout(title=title, template="plotly_dark", height=500, margin=dict(l=0, r=0, t=45, b=0))
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# LOAD REAL PIPELINE OUTPUTS
# ============================================================

comparison = load_csv("evaluation_comparison.csv")
optimized_layout = load_csv("optimized_layout.csv")
baseline_layout = load_csv("baseline_layout.csv")
warehouse = load_csv("warehouse_locations.csv")
order_routes = load_csv("optimized_routes.csv")
inventory = load_csv("inventory_snapshot.csv")

# ============================================================
# SIDEBAR MODULE NAVIGATION
# ============================================================

modules = [
    "SYSTEM OVERVIEW",
    "WAREHOUSE EXPLORER",
    "SLOTTING & INVENTORY",
    "SKU FINDER",
    "OUT-OF-STOCK PRODUCTS",
    "WHAT-IF SIMULATOR",
    "PICK ROUTES",
    "ANALYTICS",
    "CONSTRAINT VALIDATION",
    "DOWNLOADS",
    "ADVANCED ROI ANALYSIS",
]

with st.sidebar:
    selected_module = st.radio("MODULES", modules)

st.markdown(
    f"<div class='hero'><h1>WAREHOUSE INTELLIGENCE TERMINAL</h1><div>SMART SLOTting // OPTIMIZATION // ROUTE ANALYSIS</div></div>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<div class='telemetry-ribbon'><span>● SYSTEM ONLINE</span><span>SESSION {st.session_state.session_id}</span><span>{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span></div>",
    unsafe_allow_html=True,
)

# ============================================================
# MODULE 01 — SYSTEM OVERVIEW
# ============================================================

if selected_module == "SYSTEM OVERVIEW":
    optimized_distance = number_metric(comparison, "total_distance_m")
    baseline_distance = number_metric(comparison, "total_distance_m", "Baseline")
    completion = number_metric(comparison, "completion_rate")
    distance_saved = None if baseline_distance is None or optimized_distance is None else baseline_distance - optimized_distance

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("OPTIMIZED DISTANCE", display_number(optimized_distance, " m"))
    c2.metric("BASELINE DISTANCE", display_number(baseline_distance, " m"))
    c3.metric("DISTANCE SAVED", display_number(distance_saved, " m"))
    c4.metric("COMPLETION RATE", display_number(None if completion is None else completion * 100, "%"))

    if comparison is not None:
        st.subheader("BASELINE VS OPTIMIZED")
        st.dataframe(comparison, use_container_width=True)

# ============================================================
# MODULE 02 — WAREHOUSE EXPLORER
# ============================================================

elif selected_module == "WAREHOUSE EXPLORER":
    st.subheader("WAREHOUSE EXPLORER")
    if warehouse is not None:
        st.dataframe(warehouse, use_container_width=True)
        numeric = find_column(warehouse, "Distance_to_Dispatch_Depot_m", "distance")
        if numeric:
            plot_3d_category_values(warehouse.reset_index(), "index", numeric, "WAREHOUSE DISTANCE FIELD")
    else:
        st.info("Warehouse output not found. Run the pipeline first.")

# ============================================================
# MODULE 03 — SLOTTING & INVENTORY
# ============================================================

elif selected_module == "SLOTTING & INVENTORY":
    st.subheader("SLOTTING & INVENTORY")
    if optimized_layout is not None:
        st.dataframe(optimized_layout, use_container_width=True)
    else:
        st.info("Optimized layout not found. Run the pipeline first.")

# ============================================================
# MODULE 04 — SKU FINDER
# ============================================================

elif selected_module == "SKU FINDER":
    st.subheader("SKU FINDER")
    if optimized_layout is not None:
        query = st.text_input("SEARCH SKU")
        sku_col = find_column(optimized_layout, "SKU_ID", "SKU")
        result = optimized_layout
        if query and sku_col:
            result = result[result[sku_col].astype(str).str.contains(query, case=False, na=False)]
        st.dataframe(result, use_container_width=True)
    else:
        st.info("Optimized layout not found. Run the pipeline first.")

# ============================================================
# MODULE 05 — OUT OF STOCK
# ============================================================

elif selected_module == "OUT-OF-STOCK PRODUCTS":
    st.subheader("OUT-OF-STOCK PRODUCTS")
    if inventory is not None:
        units_col = find_column(inventory, "Units", "Inventory_Units", "Quantity")
        result = inventory
        if units_col:
            result = inventory[pd.to_numeric(inventory[units_col], errors="coerce").fillna(0) <= 0]
        st.dataframe(result, use_container_width=True)
        st.download_button("DOWNLOAD OUT-OF-STOCK REPORT", result.to_csv(index=False), "out_of_stock.csv", "text/csv")
    else:
        st.info("Inventory snapshot not found.")

# ============================================================
# MODULE 06 — WHAT IF
# ============================================================

elif selected_module == "WHAT-IF SIMULATOR":
    st.subheader("WHAT-IF SIMULATOR")
    st.caption("Scenario controls are estimates until connected to a rerun of the Python optimization pipeline.")
    multiplier = st.slider("DEMAND MULTIPLIER", 0.50, 2.00, 1.00, 0.05)
    if optimized_distance is not None:
        st.metric("ESTIMATED ROUTE DISTANCE", display_number(optimized_distance * multiplier, " m"))

# ============================================================
# MODULE 07 — PICK ROUTES
# ============================================================

elif selected_module == "PICK ROUTES":
    st.subheader("PICK ROUTES")
    if order_routes is not None:
        st.dataframe(order_routes, use_container_width=True)
        distance_col = find_column(order_routes, "Distance_m", "distance")
        if distance_col:
            st.plotly_chart(px.histogram(order_routes, x=distance_col, title="PICK ROUTE DISTANCES"), use_container_width=True)
    else:
        st.info("Optimized route output not found.")

# ============================================================
# MODULE 08 — ANALYTICS
# ============================================================

elif selected_module == "ANALYTICS":
    st.subheader("ANALYTICS")
    if comparison is not None:
        st.dataframe(comparison, use_container_width=True)
    if optimized_layout is not None:
        numeric_cols = optimized_layout.select_dtypes(include=np.number).columns.tolist()
        if numeric_cols:
            st.bar_chart(optimized_layout[numeric_cols].head(50))

# ============================================================
# MODULE 09 — VALIDATION
# ============================================================

elif selected_module == "CONSTRAINT VALIDATION":
    st.subheader("CONSTRAINT VALIDATION")
    violations = load_csv("optimized_violations.csv")
    if violations is not None:
        st.dataframe(violations, use_container_width=True)
    else:
        st.info("Validation output not found. Run the pipeline/validation scripts first.")

# ============================================================
# MODULE 10 — DOWNLOADS
# ============================================================

elif selected_module == "DOWNLOADS":
    st.subheader("DOWNLOADS")
    files = sorted(DATA.glob("*.csv"))
    if not files:
        st.info("No processed CSV outputs available.")
    for path in files:
        data = path.read_bytes()
        st.download_button(f"DOWNLOAD {path.name}", data, path.name, "text/csv", key=path.name)

# ============================================================
# MODULE 11 — ROI
# ============================================================

elif selected_module == "ADVANCED ROI ANALYSIS":
    st.subheader("ADVANCED ROI ANALYSIS")
    distance_saved = None
    if comparison is not None:
        baseline_distance = number_metric(comparison, "total_distance_m", "Baseline")
        optimized_distance = number_metric(comparison, "total_distance_m", "Optimized")
        if baseline_distance is not None and optimized_distance is not None:
            distance_saved = baseline_distance - optimized_distance
    walking_cost = st.number_input("COST PER WALKING METER", min_value=0.0, value=0.05, step=0.01)
    implementation_cost = st.number_input("IMPLEMENTATION COST", min_value=0.0, value=1000.0, step=100.0)
    if distance_saved is not None:
        estimated_saving = distance_saved * walking_cost
        st.metric("ESTIMATED SAVING / EVALUATION", display_number(estimated_saving))
        if estimated_saving > 0:
            st.metric("SIMPLE PAYBACK EVALUATIONS", display_number(implementation_cost / estimated_saving))

st.markdown("---")
st.caption("SnakeCharmers // Warehouse Optimization Intelligence Terminal")
