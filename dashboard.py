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


def build_robot_figure(theme):
    """Stylized 3D warehouse robot proxy; this is not a live device feed."""
    fig = go.Figure()

    def ball(x, y, z, size, color, label):
        fig.add_trace(go.Scatter3d(
            x=[x], y=[y], z=[z], mode="markers",
            marker=dict(size=size, color=color, line=dict(color="#000", width=1)),
            name=label,
            hovertemplate=f"{label}<br>XYZ: {x}, {y}, {z}<extra></extra>",
        ))

    ball(0, 0, 1.25, 34, "#333333", "Chassis")
    ball(0, 0, 2.05, 27, theme["secondary"], "Sensor array")
    ball(-0.22, -0.19, 2.10, 6, theme["accent"], "Left sensor")
    ball(0.22, -0.19, 2.10, 6, theme["accent"], "Right sensor")
    ball(0, 0, 2.48, 5, theme["danger"], "Status beacon")
    ball(-0.48, 0, 1.35, 13, "#111111", "Left drive")
    ball(0.48, 0, 1.35, 13, "#111111", "Right drive")

    theta = np.linspace(0, 2 * np.pi, 61)
    fig.add_trace(go.Scatter3d(
        x=0.65 * np.cos(theta), y=0.65 * np.sin(theta),
        z=np.full(len(theta), 0.45), mode="lines",
        line=dict(color=theme["secondary"], width=2),
        name="Navigation radius",
    ))
    fig.add_trace(go.Scatter3d(
        x=[0, 0, None, 0, 0.85], y=[0, -1.3, None, 0, 0],
        z=[2.05, 1.4, None, 2.05, 1.65], mode="lines",
        line=dict(color=theme["accent"], width=2, dash="dot"),
        name="Illustrative scan beam",
    ))
    fig.update_layout(
        height=390, margin=dict(l=0, r=0, t=36, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="monospace", color=theme["text"]), showlegend=False,
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            zaxis=dict(visible=False), bgcolor="rgba(0,0,0,0)",
            aspectmode="manual", aspectratio=dict(x=1, y=1, z=1.1),
        ),
        title=dict(text="3D DIAGNOSTIC PROXY // NOT LIVE TELEMETRY",
                   x=0.03, font=dict(size=13, color=theme["accent"])),
    )
    return fig


def assistant_reply(question):
    """Rule-based dashboard hints; intentionally not represented as an AI model."""
    q = question.lower()
    if any(k in q for k in ["slot", "allocation", "sku", "inventory"]):
        return "Review Slotting & Inventory, the baseline/optimized layouts, and unallocated SKU output. Missing inventory values should remain unknown."
    if any(k in q for k in ["route", "pick", "distance", "travel"]):
        return "Open Pick Routes to inspect route records and distance distributions. Compare baseline and optimized outputs only when both are available."
    if any(k in q for k in ["what if", "simulate", "scenario", "change"]):
        return "Use What-If Simulator for an illustrative estimate. Its sliders do not rerun the optimization solver."
    if any(k in q for k in ["validation", "safe", "hazard", "error", "violation"]):
        return "Open Constraint Validation and inspect both baseline and optimized reports. UNVERIFIED or missing data must not be treated as a pass."
    if any(k in q for k in ["graph", "chart", "analytics", "trend"]):
        return "Open Analytics for available comparison tables and numeric distributions. Charts depend on the pipeline files present."
    return "I can point you to dashboard modules for slotting, routes, what-if estimates, analytics, and validation. This helper uses keyword rules, not a language model."


# ============================================================
# LOAD REAL PIPELINE OUTPUTS
# ============================================================

comparison = load_csv("evaluation_comparison.csv")
optimized_layout = load_csv("optimized_layout.csv")
baseline_layout = load_csv("baseline_layout.csv")
warehouse = load_csv("warehouse_locations.csv")
order_routes = load_csv("optimized_routes.csv")
baseline_routes = load_csv("baseline_routes.csv")
inventory = load_csv("inventory_snapshot.csv")
baseline_violations = load_csv("baseline_violations.csv")
optimized_violations = load_csv("optimized_violations.csv")
unallocated_skus = load_csv("unallocated_skus.csv")

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

st.sidebar.divider()
st.sidebar.markdown("### 🤖 SYS DIAGNOSTICS")
st.sidebar.caption("RULE-BASED HELPER // NOT A GENERATIVE AI MODEL")
if "warehouse_ai_messages" not in st.session_state:
    st.session_state.warehouse_ai_messages = []
for item in st.session_state.warehouse_ai_messages[-4:]:
    with st.sidebar.chat_message(item["role"]):
        st.write(item["content"])
question = st.sidebar.chat_input("ASK ABOUT A DASHBOARD MODULE...", key="warehouse_ai_input")
if question:
    st.session_state.warehouse_ai_messages.append({"role": "user", "content": question})
    st.session_state.warehouse_ai_messages.append({"role": "assistant", "content": assistant_reply(question)})
    st.rerun()

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

    robot_col, diagnostic_col = st.columns([1, 1.35])
    with robot_col:
        st.plotly_chart(build_robot_figure(theme), use_container_width=True, config={"displayModeBar": True})
    with diagnostic_col:
        st.subheader("DIAGNOSTIC VISUALIZATION")
        st.write("Interactive 3D illustration for interface context.")
        st.info("This is a stylized proxy, not a live robot, camera feed, or telemetry source.")

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
    st.caption("Capacity-only estimate. These controls do not rerun the allocation optimizer or route solver.")

    location_col = find_column(warehouse, "Location_ID", "Location") if warehouse is not None else None
    inventory_sku_col = find_column(inventory, "SKU_ID", "SKU") if inventory is not None else None
    allocated_sku_col = find_column(optimized_layout, "SKU_ID", "SKU") if optimized_layout is not None else None
    unallocated_sku_col = find_column(unallocated_skus, "SKU_ID", "SKU") if unallocated_skus is not None else None

    total_locations = int(warehouse[location_col].nunique()) if warehouse is not None and location_col else None
    current_sku_count = int(inventory[inventory_sku_col].nunique()) if inventory is not None and inventory_sku_col else None
    allocated_count = int(optimized_layout[allocated_sku_col].nunique()) if optimized_layout is not None and allocated_sku_col else None
    unallocated_count = int(unallocated_skus[unallocated_sku_col].nunique()) if unallocated_skus is not None and unallocated_sku_col else None

    if total_locations is None or total_locations <= 0 or current_sku_count is None or current_sku_count <= 0:
        st.warning("Simulation needs a warehouse location list and an inventory snapshot with SKU identifiers. Missing data is not treated as zero.")
    else:
        controls, outputs = st.columns([1, 1.4])
        with controls:
            demand_growth = st.slider("DEMAND CHANGE (%)", min_value=-20, max_value=100, value=20, step=5, key="whatif_demand_growth")
            usable_capacity = st.slider("USABLE NODES (%)", min_value=50, max_value=100, value=90, step=5, key="whatif_usable_capacity")

        projected_skus = max(0, round(current_sku_count * (1 + demand_growth / 100)))
        usable_locations = max(0, round(total_locations * usable_capacity / 100))
        estimated_allocated = min(projected_skus, usable_locations)
        estimated_overflow = max(0, projected_skus - usable_locations)
        estimated_coverage = estimated_allocated / projected_skus if projected_skus else 1.0

        with outputs:
            st.markdown("#### PROJECTION OUTPUT")
            k1, k2 = st.columns(2)
            k1.metric("PROJECTED SKUS", f"{projected_skus:,}", f"{demand_growth:+d}% demand")
            k2.metric("USABLE NODES", f"{usable_locations:,}", f"{usable_capacity - 100:+d}% capacity")
            k3, k4 = st.columns(2)
            k3.metric("ESTIMATED FIT", f"{estimated_allocated:,}")
            k4.metric("ESTIMATED OVERFLOW", f"{estimated_overflow:,}", delta_color="inverse")
            st.progress(estimated_coverage, text=f"Capacity-only coverage: {estimated_coverage:.1%}")

        current_capacity_fit = min(current_sku_count, total_locations)
        comparison_df = pd.DataFrame({
            "Measure": ["SKU demand", "Usable locations", "Estimated fit", "Estimated overflow"],
            "Current snapshot": [current_sku_count, total_locations, current_capacity_fit, max(0, current_sku_count - total_locations)],
            "Scenario": [projected_skus, usable_locations, estimated_allocated, estimated_overflow],
        })
        st.dataframe(comparison_df, use_container_width=True)
        comparison_3d = comparison_df.melt(id_vars="Measure", var_name="Scenario type", value_name="Count")
        comparison_3d["Measure and scenario"] = comparison_3d["Measure"].astype(str) + " // " + comparison_3d["Scenario type"].astype(str)
        plot_3d_category_values(comparison_3d, "Measure and scenario", "Count", "ILLUSTRATIVE CAPACITY SCENARIO DELTAS")
        if allocated_count is not None:
            st.caption(f"Current optimized layout contains {allocated_count:,} distinct SKUs.")
        if unallocated_count is not None:
            st.caption(f"Unallocated SKU report contains {unallocated_count:,} distinct SKUs. The scenario estimate does not reproduce the solver's allocation decisions.")

# ============================================================
# MODULE 07 — PICK ROUTES
# ============================================================

elif selected_module == "PICK ROUTES":
    st.subheader("PICK ROUTES")
    if order_routes is not None:
        order_col = find_column(order_routes, "Order_ID", "Order")
        distance_col = find_column(order_routes, "Distance_m", "distance")
        complete_col = find_column(order_routes, "Complete", "Completed", "Completion_Status")

        if order_col:
            order_ids = order_routes[order_col].dropna().astype(str).drop_duplicates().tolist()
            if order_ids:
                selected_order = st.selectbox("INSPECT ORDER", order_ids)
                optimized_row = order_routes[order_routes[order_col].astype(str) == selected_order].iloc[0]
                baseline_row = None
                if baseline_routes is not None:
                    baseline_order_col = find_column(baseline_routes, "Order_ID", "Order")
                    if baseline_order_col:
                        matches = baseline_routes[baseline_routes[baseline_order_col].astype(str) == selected_order]
                        if not matches.empty:
                            baseline_row = matches.iloc[0]

                metric_cols = st.columns(3)
                optimized_distance = pd.to_numeric(optimized_row.get(distance_col), errors="coerce") if distance_col else np.nan
                metric_cols[0].metric("OPTIMIZED DISTANCE", display_number(optimized_distance, " m"))
                if baseline_row is not None:
                    baseline_distance = pd.to_numeric(baseline_row.get(find_column(baseline_routes, "Distance_m", "distance")), errors="coerce")
                    metric_cols[1].metric("BASELINE DISTANCE", display_number(baseline_distance, " m"))
                    if pd.notna(optimized_distance) and pd.notna(baseline_distance):
                        metric_cols[2].metric("DISTANCE DELTA", display_number(baseline_distance - optimized_distance, " m"))
                    else:
                        metric_cols[2].metric("DISTANCE DELTA", "N/A")
                else:
                    metric_cols[1].metric("BASELINE DISTANCE", "N/A")
                    metric_cols[2].metric("DISTANCE DELTA", "N/A")

                if complete_col:
                    st.caption(f"Optimized completion flag: {optimized_row.get(complete_col, 'UNKNOWN')}")
                st.markdown("#### SELECTED ORDER RECORDS")
                st.dataframe(order_routes[order_routes[order_col].astype(str) == selected_order], use_container_width=True)

        st.markdown("#### ROUTE DISTANCE DISTRIBUTION")
        if distance_col:
            st.plotly_chart(px.histogram(order_routes, x=distance_col, title="OPTIMIZED PICK ROUTE DISTANCES"), use_container_width=True)
        st.markdown("#### OPTIMIZED ROUTE RECORDS")
        st.dataframe(order_routes, use_container_width=True)
    else:
        st.info("Optimized route output not found. Run the route simulation pipeline first.")

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
    baseline_count = len(baseline_violations) if baseline_violations is not None else None
    optimized_count = len(optimized_violations) if optimized_violations is not None else None
    unallocated_count = len(unallocated_skus) if unallocated_skus is not None else None

    c1, c2, c3 = st.columns(3)
    c1.metric("BASELINE REPORT ROWS", "N/A" if baseline_count is None else f"{baseline_count:,}")
    c2.metric("OPTIMIZED REPORT ROWS", "N/A" if optimized_count is None else f"{optimized_count:,}")
    c3.metric("UNALLOCATED SKU ROWS", "N/A" if unallocated_count is None else f"{unallocated_count:,}")

    left, right = st.columns(2)
    with left:
        st.markdown("#### BASELINE VALIDATION")
        if baseline_violations is not None:
            st.dataframe(baseline_violations, use_container_width=True)
        else:
            st.info("Baseline validation report not found.")
    with right:
        st.markdown("#### OPTIMIZED VALIDATION")
        if optimized_violations is not None:
            st.dataframe(optimized_violations, use_container_width=True)
        else:
            st.info("Optimized validation report not found.")

    st.markdown("#### UNALLOCATED SKU BACKLOG")
    if unallocated_skus is not None:
        st.dataframe(unallocated_skus, use_container_width=True)
    else:
        st.info("Unallocated SKU report not found; this is unknown, not zero.")

    st.caption("These cards count report rows, not necessarily unique violations. Missing reports are shown as N/A, not as a clean validation result.")

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
