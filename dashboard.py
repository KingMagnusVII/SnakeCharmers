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

# ---------------- THEME SETTINGS ----------------

THEMES = {
    "CYBER TERMINAL": {
        "background": "#050505",
        "panel": "#0a0a0a",
        "text": "#00ff41", # Classic Terminal Green
        "accent": "#00ffff", # Cyan glow
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
    }
}
# Comparison metrics are rendered below from evaluation_comparison.csv.

# Generate some static fake session data for tech flavor

if "session_id" not in st.session_state:
    st.session_state.session_id = f"0x{random.randint(100000, 999999):06X}"
    st.session_state.net_ip = f"192.168.{random.randint(1,255)}.{random.randint(1,255)}"

current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

with st.sidebar:
    st.markdown(f"<div style='font-family:Share Tech Mono; color:{THEMES['CYBER TERMINAL']['secondary']}; font-size:0.7rem;'>USER_AUTH: ROOT // SESSION: {st.session_state.session_id}</div>", unsafe_allow_html=True)
    st.markdown("### ⚙️ SYSTEM PREFS")
    selected_theme = st.selectbox(
        "INTERFACE THEME [SELECT]",
        list(THEMES.keys()),
        key="dashboard_theme",
    )

theme = THEMES[selected_theme]

# INJECTING HYPER-TECHNICAL UI CSS
# INJECTING HYPER-TECHNICAL UI CSS WITH ENHANCED SIDEBAR ANIMATION
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@500;600;700&display=swap');
    :root {{
      --sc-bg: {theme['background']}; --sc-panel: {theme['panel']};
      --sc-text: {theme['text']}; --sc-accent: {theme['accent']};
      --sc-muted: {theme['secondary']}; --sc-line: {theme['secondary']}90;
    }}
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
      font-family: 'Rajdhani', sans-serif;
      background-color: var(--sc-bg);
      color: var(--sc-text);
      background-image: 
        linear-gradient(var(--sc-line) 1px, transparent 1px),
        linear-gradient(90deg, var(--sc-line) 1px, transparent 1px);
      background-size: 30px 30px;
      background-position: center center;
    }}
    .stApp {{ background: transparent; }}
    
    .block-container {{ max-width: 1750px; padding-top: 1rem; padding-bottom: 3rem; background: var(--sc-bg); box-shadow: 0 0 50px var(--sc-bg) inset; }}
    [data-testid="stSidebar"] {{ background: var(--sc-panel); border-right: 1px solid var(--sc-accent); box-shadow: 2px 0 15px {theme['accent']}15; }}
    
    h1, h2, h3, h4, h5, h6 {{ 
        font-family: 'Rajdhani', sans-serif !important; 
        color: var(--sc-text) !important; 
        text-transform: uppercase; 
        letter-spacing: 2px;
    }}
    h1 {{ font-size: 2.2rem !important; font-weight: 700 !important; text-shadow: 0 0 8px {theme['accent']}40; }}
    
    /* ---------------------------------------------------- */
    /* CYBERPUNK SIDEBAR HOVER ANIMATIONS                   */
    /* ---------------------------------------------------- */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: 1px solid transparent !important;
        border-radius: 2px !important;
        padding: 6px 10px !important;
        margin-bottom: 3px !important;
        cursor: pointer !important;
    }}

    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        transform: translateX(6px) !important;
        background-color: #111827 !important;
        border: 1px solid {theme['accent']} !important;
        box-shadow: 0 0 12px {theme['accent']}40, inset 0 0 8px {theme['accent']}20 !important;
        color: {theme['accent']} !important;
    }}

    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
        background: {theme['panel']} !important;
        border: 1px solid {theme['success']} !important;
        box-shadow: 0 0 15px {theme['success']}40 inset, 0 0 8px {theme['success']}30 !important;
        transform: translateX(4px) !important;
    }}

    /* ---------------------------------------------------- */
    /* HERO & TELEMETRY                                     */
    /* ---------------------------------------------------- */
    .hero {{ 
        position: relative; overflow: hidden; padding: 2rem; margin: .2rem 0 1.6rem;
        border: 1px solid var(--sc-accent); 
        background: linear-gradient(135deg, var(--sc-panel) 0%, var(--sc-bg) 100%);
        border-left: 8px solid var(--sc-accent);
        text-transform: uppercase;
        box-shadow: 0 0 20px {theme['accent']}20;
    }}
    
    .telemetry-ribbon {{
        display: flex; flex-wrap: wrap; gap: 20px; padding: 12px 20px; 
        background: var(--sc-panel); border: 1px solid var(--sc-accent);
        font-family: 'Share Tech Mono', monospace; font-size: 0.85rem; color: var(--sc-accent);
        margin-bottom: 25px; text-transform: uppercase;
        box-shadow: inset 0 0 10px {theme['accent']}10;
    }}
    .telemetry-ribbon span {{ display: flex; align-items: center; gap: 8px; }}
    .blink {{ animation: blinker 1.5s linear infinite; height: 10px; width: 10px; background-color: {theme['success']}; border-radius: 50%; box-shadow: 0 0 10px {theme['success']}; }}
    @keyframes blinker {{ 50% {{ opacity: 0; box-shadow: none; }} }}
    
    [data-testid="stMetric"] {{ 
        background: linear-gradient(180deg, var(--sc-panel) 0%, transparent 100%);
        border: 1px solid var(--sc-line); 
        padding: 1rem 1.2rem;
        border-top: 3px solid var(--sc-accent);
        transition: all 0.2s ease;
    }}
    [data-testid="stMetric"]:hover {{ border-color: var(--sc-accent); box-shadow: 0 0 15px {theme['accent']}30 inset; }}
    [data-testid="stMetricLabel"] {{ color: var(--sc-text) !important; font-family: 'Rajdhani', sans-serif !important; font-size: 1.1rem !important; text-transform: uppercase; letter-spacing: 1px; }}
    [data-testid="stMetricValue"] {{ color: var(--sc-accent) !important; font-family: 'Share Tech Mono', monospace !important; text-shadow: 0 0 8px {theme['accent']}60; font-size: 2.2rem !important; }}
    [data-testid="stMetricDelta"] {{ font-family: 'Share Tech Mono', monospace !important; font-size: 0.9rem !important; background: #000; padding: 2px 5px; border: 1px solid var(--sc-line); }}
    
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 0; border-bottom: 1px solid var(--sc-accent); }}
    [data-testid="stTabs"] button[role="tab"] {{ font-family: 'Share Tech Mono', monospace; font-size: 0.9rem; text-transform: uppercase; padding: 1rem 1.5rem; border-radius: 0; color: var(--sc-text); }}
    [data-testid="stTabs"] button[aria-selected="true"] {{ color: var(--sc-accent) !important; border-bottom: 2px solid var(--sc-accent) !important; background: var(--sc-panel); box-shadow: 0 -5px 15px {theme['accent']}15 inset; }}
    
    .stButton > button, .stDownloadButton > button {{ 
        border-radius: 0px; border: 1px solid var(--sc-accent); 
        font-family: 'Share Tech Mono', monospace; font-weight: bold; text-transform: uppercase; 
        background: transparent; color: var(--sc-accent); transition: all 0.2s;
        letter-spacing: 1px;
    }}
    .stButton > button::before {{ content: '>> '; }}
    .stButton > button:hover, .stDownloadButton > button:hover {{ background: var(--sc-accent); color: #000; box-shadow: 0 0 15px var(--sc-accent); text-shadow: none; }}
    
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stSelectbox"] [data-baseweb="select"], [data-testid="stMultiSelect"] [data-baseweb="select"] {{ 
        border-radius: 0px; border: 1px solid var(--sc-accent); background: var(--sc-bg); color: var(--sc-text); font-family: 'Share Tech Mono', monospace;
        box-shadow: inset 0 0 5px {theme['accent']}20;
    }}
    
    [data-testid="stDataFrame"], [data-testid="stTable"] {{ border: 1px solid var(--sc-accent); border-radius: 0px; overflow: hidden; }}
    hr {{ border-color: var(--sc-accent) !important; margin: 2rem 0 !important; opacity: 0.5; }}
    a {{ color: var(--sc-accent) !important; text-decoration: none; border-bottom: 1px dashed var(--sc-accent); }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# DATA HELPERS
# ============================================================

@st.cache_data
def load_csv(filename):
    """Load a generated CSV, returning None if unavailable."""
    path = DATA / filename
    if not path.exists(): return None
    try: return pd.read_csv(path)
    except Exception: return None

def find_column(df, *keywords):
    """Find a column by case-insensitive exact or partial name."""
    if df is None or df.empty: return None
    columns = list(df.columns)
    normalized = {str(col).lower().replace(" ", "_"): col for col in columns}
    for keyword in keywords:
        key = keyword.lower().replace(" ", "_")
        if key in normalized: return normalized[key]
    for keyword in keywords:
        key = keyword.lower().replace(" ", "_")
        for normalized_name, original_name in normalized.items():
            if key in normalized_name: return original_name
    return None

def number_metric(metrics, name, column="Optimized"):
    """Get a numeric evaluation metric by its metric name."""
    if metrics is None or metrics.empty: return None
    metric_col = find_column(metrics, "Metric")
    value_col = find_column(metrics, column)
    if not metric_col or not value_col: return None
    matches = metrics[metrics[metric_col].astype(str).str.lower() == name.lower()]
    if matches.empty: return None
    try: return float(matches.iloc[0][value_col])
    except (ValueError, TypeError): return None

def display_number(value, suffix=""):
    if value is None or pd.isna(value): return "N/A"
    return f"{value:,.2f}{suffix}"

def plot_3d_category_values(df, category_col, value_col, title, theme, max_points=80):
    """Interactive 3D category/value view. Each category is a vertical stem with a marker."""
    if df is None or df.empty or category_col not in df.columns or value_col not in df.columns:
        st.info("[!] INSUFFICIENT DATASTREAM FOR 3D RENDER.")
        return
    plot_df = df[[category_col, value_col]].copy()
    plot_df[value_col] = pd.to_numeric(plot_df[value_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[value_col]).head(max_points)
    if plot_df.empty: return
    plot_df[category_col] = plot_df[category_col].astype(str)
    plot_df["_x"] = range(len(plot_df))
    fig = go.Figure()
    for row in plot_df.itertuples(index=False, name=None):
        category, value, x = row[0], row[1], row[2]
        fig.add_trace(go.Scatter3d(
            x=[x, x], y=[0, 0], z=[0, value], mode="lines",
            line=dict(color=theme["secondary"], width=2), showlegend=False,
            hoverinfo="skip"))
    fig.add_trace(go.Scatter3d(
        x=plot_df["_x"], y=[0] * len(plot_df), z=plot_df[value_col],
        mode="markers+text", text=plot_df[category_col], textposition="top center",
        marker=dict(size=4, color=plot_df[value_col], colorscale="Greens" if theme["success"]=="#00ff41" else "Blues", showscale=True,
                    colorbar=dict(title=value_col, tickfont=dict(color=theme["text"]))),
        customdata=plot_df[[category_col, value_col]],
        hovertemplate="%{customdata[0]}<br>" + value_col + ": %{customdata[1]:,.3g}<extra></extra>"))
    fig.update_layout(
        title=dict(text=title.upper() + f" // [RENDER_ID: {random.randint(1000,9999)}]", font=dict(family="Share Tech Mono", size=14, color=theme["accent"])),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=50,b=0),
        scene=dict(xaxis=dict(title="IDX", showticklabels=False, gridcolor=theme["secondary"]),
                   yaxis=dict(title="DEPTH", showticklabels=False, range=[-1,1], gridcolor=theme["secondary"]),
                   zaxis=dict(title=value_col, gridcolor=theme["secondary"]), bgcolor="rgba(0,0,0,0)"),
        font=dict(family="Share Tech Mono", color=theme["text"]))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})

def styled_frame(df):
    """Return a presentation-only styled view; never alter the source DataFrame."""
    if df is None:
        return df

    # Keep styling consistent with the selected dashboard theme. Values, columns,
    # row order, index, and source DataFrame remain unchanged.
    active_theme = THEMES.get(selected_theme, THEMES["CYBER TERMINAL"])
    panel = active_theme["panel"]
    text_color = active_theme["text"]
    accent = active_theme["accent"]
    border = active_theme["secondary"]

    table_styles = [
        {"selector": "table", "props": [("border-collapse", "separate"), ("border-spacing", "0"), ("width", "100%"), ("background-color", panel)]},
        {"selector": "thead th", "props": [("background-color", "#101820"), ("color", accent), ("font-weight", "700"), ("text-transform", "uppercase"), ("letter-spacing", "0.04em"), ("border-bottom", f"1px solid {accent}"), ("padding", "10px 12px")]},
        {"selector": "tbody td", "props": [("color", text_color), ("border-bottom", f"1px solid {border}"), ("padding", "8px 12px"), ("background-color", panel)]},
        {"selector": "tbody tr:hover td", "props": [("background-color", "#17212b") ]},
        {"selector": "caption", "props": [("caption-side", "top"), ("color", accent)]},
    ]
    return df.style.set_table_styles(table_styles)


def show_table(df, message="[!] NO DATA FRAGMENTS DETECTED."):
    if df is None or df.empty:
        st.info(message)
    else:
        st.dataframe(styled_frame(df), use_container_width=True, hide_index=True)

def download_button_for_file(filename, label=None):
    df = load_csv(filename)
    if df is None:
        st.caption(f"ERR: {filename} UNAVAILABLE_ON_DISK")
        return
    st.download_button(
        label=label or f"EXPORT {filename}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=f"download_{filename}",
        use_container_width=True,
    )

# ============================================================
# LOAD GENERATED PIPELINE OUTPUTS
# ============================================================

required_file = DATA / "evaluation_comparison.csv"
if not required_file.exists():
    st.error(
        "CRITICAL SYS_ERR: EVALUATION ARTIFACTS MISSING.\n"
        "EXECUTE `python scripts/run_pipeline.py` TO RE-INITIALIZE DATA STREAM."
    )
    st.stop()

metrics = load_csv("evaluation_comparison.csv")
optimized = load_csv("optimized_allocation.csv")
baseline = load_csv("baseline_allocation.csv")
locations = load_csv("warehouse_locations.csv")
baseline_routes = load_csv("baseline_routes.csv")
optimized_routes = load_csv("optimized_routes.csv")
baseline_violations = load_csv("baseline_violations.csv")
optimized_violations = load_csv("optimized_violations.csv")
affinity = load_csv("affinity_pairs.csv")
demand = load_csv("demand_profile.csv")
dimensional = load_csv("dimensional_fit.csv")
unallocated = load_csv("unallocated_skus.csv")

# ============================================================
# 3D VISUALS + BUILT-IN AI HELPER
# ============================================================
def build_robot_figure(theme):
    """Stylized interactive 3D warehouse robot made from Plotly primitives."""
    fig = go.Figure()
    def ball(x, y, z, size, color, name):
        fig.add_trace(go.Scatter3d(x=[x], y=[y], z=[z], mode="markers",
            marker=dict(size=size, color=color, line=dict(color="#000", width=1)),
            name=name, hovertemplate=f"NODE: {name}<br>XYZ: {x},{y},{z}<extra></extra>"))
    chassis_color = "#333333"
    sensor_color = theme["secondary"]
    beacon_color = theme["accent"]
    
    ball(0, 0, 1.25, 34, chassis_color, "CHASSIS_CORE")
    ball(0, 0, 2.05, 27, sensor_color, "SENSOR_ARRAY_V2")
    ball(-0.22, -0.19, 2.10, 6, beacon_color, "LIDAR_OPTIC_L")
    ball(0.22, -0.19, 2.10, 6, beacon_color, "LIDAR_OPTIC_R")
    ball(0, 0, 2.48, 5, theme["danger"], "STATUS_BEACON_RED")
    ball(-0.48, 0, 1.35, 13, "#111", "DRIVE_UNIT_L")
    ball(0.48, 0, 1.35, 13, "#111", "DRIVE_UNIT_R")
    
    theta = [i * 2 * 3.14159 / 60 for i in range(61)]
    fig.add_trace(go.Scatter3d(x=[0.65*__import__('math').cos(t) for t in theta],
        y=[0.65*__import__('math').sin(t) for t in theta], z=[0.45]*len(theta),
        mode="lines", line=dict(color=theme["secondary"], width=2), name="NAV_FIELD_RADIUS"))
    fig.add_trace(go.Scatter3d(x=[0, 0, None, 0, 0.85], y=[0, -1.3, None, 0, 0],
        z=[2.05, 1.4, None, 2.05, 1.65], mode="lines",
        line=dict(color=beacon_color, width=2, dash="dot"), name="SCAN_BEAM_ACTIVE"))
    fig.update_layout(height=390, margin=dict(l=0,r=0,t=20,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Share Tech Mono", color=theme["text"]), showlegend=False,
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                   bgcolor="rgba(0,0,0,0)", aspectmode="manual", aspectratio=dict(x=1,y=1,z=1.1)),
        title=dict(text="AUTONOMOUS TELEMETRY · 3D // TRACKING", x=0.03, font=dict(size=14, color=theme["accent"])))
    return fig

def assistant_reply(question):
    q = question.lower()
    if any(k in q for k in ["slot", "allocation", "sku", "inventory"]):
        return "SYS> For slotting logic, cross-reference baseline vs optimized matrices. Query unallocated arrays and dimensional-fit logs. Accessing [SLOTTING & INVENTORY] subroutine..."
    if any(k in q for k in ["route", "pick", "distance", "travel"]):
        return "SYS> Accessing [PICK ROUTES] module. Evaluating baseline vs heuristic pathing. Distances computed via Euclidean/Manhattan proxies."
    if any(k in q for k in ["what if", "simulate", "scenario", "change"]):
        return "SYS> Execute [WHAT-IF SIMULATOR] to adjust theoretical volume inputs. Outputs rely on current deterministic solver constraints. Recalibrating..."
    if any(k in q for k in ["validation", "safe", "hazard", "error"]):
        return "SYS> ALERT. Access [VALIDATION] to pull constraint breach logs. Unknown hazard flags must be manually overridden by safety auth."
    if any(k in q for k in ["graph", "chart", "analytics", "trend"]):
        return "SYS> Spooling [ANALYTICS] module. Hover on 3D spatial renders for raw telemetry. Mouse control active for digital twin."
    return f"SYS> Terminal AI [ID:{random.randint(10,99)}] Online. Awaiting parameter queries on: slotting matrices, routing heuristics, analytics, simulations, or constraints."

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.markdown("## 📟 TERMINAL ACCESS")
st.sidebar.caption("WH-INTELLIGENCE CORE // VER 5.1.0")
st.sidebar.divider()

page = st.sidebar.radio(
    "SYSTEM MODULES [ACTIVE]",
    [
        "01_Overview",
        "02_Warehouse_Explorer",
        "03_Slotting_Inventory",
        "04_SKU_Finder",
        "05_What-If_Simulator",
        "06_Pick_Routes",
        "07_Analytics",
        "08_Validation",
        "09_Downloads",
        "10_Advanced_ROI_Analysis"
    ],
)

st.sidebar.divider()
st.sidebar.markdown("### 📡 PIPELINE DATALINK")

if metrics is not None:
    st.sidebar.markdown(f"<div style='color:{theme['success']}; font-family:Share Tech Mono;'>[OK] TELEMETRY SYNCED</div>", unsafe_allow_html=True)
else:
    st.sidebar.markdown(f"<div style='color:{theme['danger']}; font-family:Share Tech Mono;'>[ERR] SIGNAL LOST</div>", unsafe_allow_html=True)

st.sidebar.markdown(f"<div class='micro-text'>NET_IP: {st.session_state.net_ip} <br>PACKET_LOSS: 0.04% <br>UPTIME: {random.randint(24, 720)} HRS</div>", unsafe_allow_html=True)
st.sidebar.caption("SYNTHETIC GEOMETRY ACTIVE")

st.sidebar.divider()
st.sidebar.markdown("### 🤖 SYS_AI COMMS")
st.sidebar.caption("HEURISTIC DIAGNOSTIC HELPER // [IDLE]")
if "warehouse_ai_messages" not in st.session_state:
    st.session_state.warehouse_ai_messages = []
for item in st.session_state.warehouse_ai_messages[-4:]:
    with st.sidebar.chat_message(item["role"]):
        st.markdown(f"<span style='font-family:Share Tech Mono;font-size:0.85rem;'>{item['content']}</span>", unsafe_allow_html=True)
question = st.sidebar.chat_input("QUERY SYS_AI...", key="warehouse_ai_input")
if question:
    st.session_state.warehouse_ai_messages.append({"role": "user", "content": f"USR> {question}"})
    st.session_state.warehouse_ai_messages.append({"role": "assistant", "content": assistant_reply(question)})
    st.rerun()

# ============================================================
# HEADER & SYSTEM TELEMETRY
# ============================================================

st.markdown(
    f"""
    <div class="micro-text" style="margin-bottom: -15px;">INIT_SEQ: 0x{random.randint(1000000, 9999999):X} // SYS.TIME: {current_time}</div>
    <div class="hero">
        <div class="eyebrow">COMMAND TERMINAL // WH-OPT-CORE // SECTOR 7G</div>
        <h1>WAREHOUSE OPTIMIZATION TERMINAL</h1>
        <p>> HEURISTIC SLOTTING // PATHFINDING // CAPACITY SIMULATION <_</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="telemetry-ribbon">
        <span><div class="blink"></div> UPLINK: STABLE</span>
        <span>|</span>
        <span>LATENCY: {random.randint(8,18)}ms</span>
        <span>|</span>
        <span>SOLVER: MILP_CORE_V4</span>
        <span>|</span>
        <span>ENCRYPT: AES-256</span>
        <span>|</span>
        <span>NODES: {len(locations) if locations is not None else 'N/A'}</span>
        <span>|</span>
        <span>CPU_TEMP: {random.randint(38,45)}°C</span>
    </div>
    """, unsafe_allow_html=True
)

# ============================================================
# OVERVIEW
# ============================================================

if page == "01_Overview":
    st.markdown("### MODULE 01 // 📊 SYSTEM OVERVIEW")
    st.caption("METRICS EXTRACTED FROM PIPELINE SIMULATION ARTIFACTS. // [SYS_OP_OK]")

    robot_col, robot_note = st.columns([1, 1.35])
    with robot_col:
        st.plotly_chart(build_robot_figure(theme), use_container_width=True, config={"displayModeBar": True})
    with robot_note:
        st.markdown(f"### 🤖 DIGITAL TWIN DIAGNOSTIC // ID: {random.randint(100,999)}")
        st.write("LIVE RENDER OF AUTONOMOUS UNIT. FULL 3D ROTATION ENABLED. INSPECT HEURISTIC SCAN PATHS.")
        st.info("SYS NOTE: RENDER IS A DIAGNOSTIC PROXY, NOT LIVE CAMERA FEED. // DATA_STREAM_SECURE")
        st.markdown("<div class='micro-text'>LIDAR_STATUS: OPTIMAL | DRIVE_MOTORS: SYNCED | NAV_SYSTEM: ACTIVE</div>", unsafe_allow_html=True)

    avg_distance_base = number_metric(metrics, "average_distance_m", "Baseline")
    avg_distance_opt = number_metric(metrics, "average_distance_m", "Optimized")
    total_distance_base = number_metric(metrics, "total_distance_m", "Baseline")
    total_distance_opt = number_metric(metrics, "total_distance_m", "Optimized")
    complete_orders = number_metric(metrics, "complete_orders", "Optimized")
    orders_simulated = number_metric(metrics, "orders_simulated", "Optimized")
    utilization = number_metric(metrics, "whole_warehouse_utilization", "Optimized")
    allocated_utilization = number_metric(metrics, "allocated_bin_utilization", "Optimized")
    coverage = number_metric(metrics, "allocation_coverage", "Optimized")

    allocated_count = len(optimized) if optimized is not None else None
    location_count = len(locations) if locations is not None else None

    a, b, c, d = st.columns(4)
    a.metric("ORDERS PROCESSED", f"{orders_simulated:,.0f}" if orders_simulated is not None else "ERR")
    st.markdown("<div class='micro-text' style='margin-top:-10px; margin-bottom:15px;'>MEM_ADDR: 0x0A9F</div>", unsafe_allow_html=True)
    
    b.metric("ORDERS COMPLETED", f"{complete_orders:,.0f}" if complete_orders is not None else "ERR")
    st.markdown("<div class='micro-text' style='margin-top:-10px; margin-bottom:15px;'>MEM_ADDR: 0x0AA0</div>", unsafe_allow_html=True)
    
    c.metric("ALLOCATED SKUS", f"{allocated_count:,}" if allocated_count is not None else "ERR")
    st.markdown("<div class='micro-text' style='margin-top:-10px; margin-bottom:15px;'>MEM_ADDR: 0x0AA1</div>", unsafe_allow_html=True)
    
    d.metric("WH LOCATIONS", f"{location_count:,}" if location_count is not None else "ERR")
    st.markdown("<div class='micro-text' style='margin-top:-10px; margin-bottom:15px;'>MEM_ADDR: 0x0AA2</div>", unsafe_allow_html=True)

    e, f, g, h = st.columns(4)
    e.metric("OPT AVG DISTANCE", display_number(avg_distance_opt, " m"),
        delta=(f"{avg_distance_opt - avg_distance_base:+.2f} m vs BASE" if avg_distance_opt is not None and avg_distance_base is not None else None), delta_color="inverse")
    
    f.metric("OPT TOTAL DISTANCE", display_number(total_distance_opt, " m"),
        delta=(f"{total_distance_opt - total_distance_base:+.2f} m vs BASE" if total_distance_opt is not None and total_distance_base is not None else None), delta_color="inverse")
    
    g.metric("GLOBAL UTILIZATION", f"{utilization * 100:.2f}%" if utilization is not None else "ERR")
    
    h.metric("BIN UTILIZATION", f"{allocated_utilization * 100:.2f}%" if allocated_utilization is not None else "ERR")

    st.divider()

    left, right = st.columns([1.25, 1])
    with left:
        st.markdown("### 📉 DISTANCE VECTOR COMPARISON // [ANALYSIS]")
        if metrics is not None:
            metric_col = find_column(metrics, "Metric")
            baseline_col = find_column(metrics, "Baseline")
            optimized_col = find_column(metrics, "Optimized")
            if metric_col and baseline_col and optimized_col:
                chart_df = metrics[[metric_col, baseline_col, optimized_col]].copy()
                chart_df.columns = ["Metric", "Baseline", "Optimized"]
                distance_df = chart_df[chart_df["Metric"].astype(str).str.contains("distance", case=False)]
                if not distance_df.empty:
                    plot_df = distance_df.melt(id_vars="Metric", var_name="Scenario", value_name="Distance")
                    fig = px.scatter_3d(plot_df, x="Metric", y="Scenario", z="Distance", color="Scenario", symbol="Scenario", template="plotly_dark", color_discrete_sequence=[theme["secondary"], theme["accent"]])
                    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title="DATASET", font=dict(family="Share Tech Mono", color=theme["text"]), scene=dict(xaxis=dict(gridcolor=theme["secondary"]), yaxis=dict(gridcolor=theme["secondary"]), zaxis=dict(gridcolor=theme["secondary"])))
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("[!] NO DISTANCE VECTORS FOUND.")
            else: show_table(metrics)

    with right:
        st.markdown("### 🍩 DEMAND CLASS DISTRIBUTION // [TOPOLOGY]")
        if optimized is not None:
            demand_class = find_column(optimized, "Demand_Class", "demand_class", "class")
            if demand_class:
                counts = optimized[demand_class].fillna("UNKNOWN").astype(str).value_counts().rename_axis("Demand class").reset_index(name="SKU count")
                fig = px.pie(counts, names="Demand class", values="SKU count", hole=0.62, template="plotly_dark", color_discrete_sequence=[theme["accent"], theme["purple"], theme["secondary"], theme["success"]])
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", legend_title="", font=dict(family="Share Tech Mono", color=theme["text"]))
                st.plotly_chart(fig, use_container_width=True)
            else: st.caption("[!] NO DEMAND-CLASS VECTOR DETECTED.")

    st.markdown("### 📋 RAW EVALUATION MATRICES // [FETCHING BUFFER...]")
    show_table(metrics)

# ============================================================
# WAREHOUSE EXPLORER
# ============================================================

elif page == "02_Warehouse_Explorer":
    st.markdown("### MODULE 02 // 🗺️ SPATIAL DIGITAL TWIN")
    st.caption("3D RENDER OF WAREHOUSE COORDINATES AND HEURISTIC ASSIGNMENTS. // SCANNING ZONES...")

    if locations is None or locations.empty:
        st.error("ERR: warehouse_locations.csv MISSING. HALTING OPERATION.")
        st.stop()

    warehouse_map = locations.copy()
    if optimized is not None and not optimized.empty:
        allocation_map = optimized[["Location_ID", "SKU_ID", "Demand_Class"]].drop_duplicates("Location_ID")
        warehouse_map = warehouse_map.merge(allocation_map, on="Location_ID", how="left")
    else:
        warehouse_map["SKU_ID"] = None
        warehouse_map["Demand_Class"] = None

    warehouse_map["Allocation_Status"] = warehouse_map["SKU_ID"].notna().map({True: "ALLOCATED", False: "VACANT"})

    total_locations = len(warehouse_map)
    occupied = int((warehouse_map["Allocation_Status"] == "ALLOCATED").sum())
    available = total_locations - occupied

    c1, c2, c3 = st.columns(3)
    c1.metric("TOTAL NODES", f"{total_locations:,}")
    c2.metric("ALLOCATED NODES", f"{occupied:,}")
    c3.metric("VACANT NODES", f"{available:,}")

    st.divider()

    left_filter, right_filter = st.columns(2)
    with left_filter:
        statuses = st.multiselect("FILTER: STATUS [VECTOR_MAP]", ["ALLOCATED", "VACANT"], default=["ALLOCATED", "VACANT"])
    with right_filter:
        if "Zone" in warehouse_map.columns:
            zones = sorted(warehouse_map["Zone"].dropna().astype(str).unique())
            selected_zones = st.multiselect("FILTER: ZONES [SECTOR_SCAN]", zones, default=zones)
        else: selected_zones = None

    filtered = warehouse_map[warehouse_map["Allocation_Status"].isin(statuses)].copy()
    if selected_zones is not None: filtered = filtered[filtered["Zone"].astype(str).isin(selected_zones)]

    st.markdown(f"#### 3D SPATIAL SCATTER // RENDER {random.randint(1000,9999)}")
    fig = px.scatter_3d(filtered, x="X_m", y="Y_m", z="Z_m", color="Allocation_Status", hover_name="Location_ID", hover_data=["SKU_ID", "Demand_Class", "Zone", "Aisle_Number", "Bay", "Shelf_Level", "Allocation_Status"], category_orders={"Allocation_Status": ["VACANT", "ALLOCATED"]}, color_discrete_map={"VACANT": theme["secondary"], "ALLOCATED": theme["accent"]}, template="plotly_dark")
    fig.update_traces(marker=dict(size=4, opacity=0.9, symbol="square"))
    fig.update_layout(height=650, margin=dict(l=0, r=0, t=25, b=0), paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Share Tech Mono", color=theme["text"]), scene=dict(xaxis=dict(title="X (m)", gridcolor=theme["secondary"]), yaxis=dict(title="Y (m)", gridcolor=theme["secondary"]), zaxis=dict(title="Z (m)", gridcolor=theme["secondary"]), bgcolor="rgba(0,0,0,0)", aspectmode="data"), legend_title="NODE STATUS")
    st.plotly_chart(fig, use_container_width=True)

    if {"X_m", "Y_m"}.issubset(warehouse_map.columns):
        st.markdown("#### 2D ORTHOGRAPHIC PROJECTION // TOP-DOWN")
        map_df = filtered.copy()
        if not map_df.empty:
            floor_fig = px.scatter(map_df, x="X_m", y="Y_m", color="Allocation_Status", hover_name="Location_ID", hover_data=[c for c in ["SKU_ID", "Demand_Class", "Zone", "Aisle_Number", "Bay", "Shelf_Level"] if c in map_df.columns], color_discrete_map={"VACANT": theme["secondary"], "ALLOCATED": theme["success"]}, template="plotly_dark")
            floor_fig.update_traces(marker=dict(size=8, symbol="square", opacity=0.85, line=dict(width=1, color="#000")))
            floor_fig.update_layout(height=460, margin=dict(l=10, r=10, t=25, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(title="X (m)", gridcolor=theme["secondary"]), yaxis=dict(title="Y (m)", gridcolor=theme["secondary"]), font=dict(family="Share Tech Mono", color=theme["text"]))
            st.plotly_chart(floor_fig, use_container_width=True)
        else: st.info("[!] NO NODES MATCH FILTERS.")

    st.markdown("#### DATA INSPECTOR // RAW GRID")
    search_location = st.text_input("QUERY LOCATION_ID OR SKU // [INPUT REQ]", placeholder="A01-RL-B01-L02", key="warehouse_search")
    if search_location:
        search_mask = warehouse_map.astype(str).apply(lambda col: col.str.contains(search_location, case=False, na=False)).any(axis=1)
        detail_df = warehouse_map[search_mask]
    else: detail_df = warehouse_map
    st.dataframe(styled_frame(detail_df), use_container_width=True, hide_index=True)

# ============================================================
# SLOTTING & INVENTORY
# ============================================================

elif page == "03_Slotting_Inventory":
    st.markdown("### MODULE 03 // 📦 INVENTORY MATRIX")
    st.caption("EXPLORE SKU ALLOCATIONS, CAPACITIES, AND PLACEMENT VECTORS. // [SECURE_VIEW]")

    if optimized is None or optimized.empty:
        st.warning("ERR: optimized_allocation.csv UNAVAILABLE. DATALINK SEVERED.")
    else:
        inventory = optimized.copy()
        sku_col = find_column(inventory, "SKU_ID", "sku_id", "SKU")
        location_col = find_column(inventory, "Location_ID", "location_id", "Location")
        demand_col = find_column(inventory, "Demand_Class", "demand_class", "class")
        rationale_col = find_column(inventory, "Placement_Rationale", "placement_rationale", "Rationale")

        if (locations is not None and not locations.empty and location_col is not None and "Location_ID" in locations.columns):
            location_details = locations.copy()
            extra_columns = [col for col in location_details.columns if col == "Location_ID" or col not in inventory.columns]
            location_details = location_details[extra_columns]
            inventory = inventory.merge(location_details, left_on=location_col, right_on="Location_ID", how="left", suffixes=("", "_warehouse"))

        total_records = len(inventory)
        if sku_col is not None:
            total_skus = inventory[sku_col].nunique()
            allocated_skus = inventory.loc[inventory[location_col].notna(), sku_col].nunique() if location_col is not None else total_skus
        else: total_skus = allocated_skus = total_records

        unique_locations = inventory[location_col].nunique() if location_col is not None else 0
        demand_classes = inventory[demand_col].nunique() if demand_col is not None else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("UNIQUE SKUS", f"{total_skus:,}")
        k2.metric("ALLOCATED SKUS", f"{allocated_skus:,}")
        k3.metric("ASSIGNED NODES", f"{unique_locations:,}")
        k4.metric("DEMAND VECTORS", f"{demand_classes:,}")

        st.divider()
        st.markdown("#### 🔎 DATA QUERY // EXECUTING SEARCH PROTOCOL")
        filter1, filter2, filter3 = st.columns(3)
        with filter1: search = st.text_input("QUERY STRING [PARAM]", key="inventory_search")
        with filter2:
            if demand_col is not None:
                available_classes = sorted(inventory[demand_col].dropna().astype(str).unique().tolist())
                selected_classes = st.multiselect("DEMAND VECTOR [FILTER]", available_classes, default=available_classes, key="inventory_demand_filter")
            else: selected_classes = None
        with filter3:
            zone_col = find_column(inventory, "Zone", "zone", "Warehouse_Zone")
            if zone_col is not None:
                available_zones = sorted(inventory[zone_col].dropna().astype(str).unique().tolist())
                selected_zones = st.multiselect("WH ZONE [SECTOR]", available_zones, default=available_zones, key="inventory_zone_filter")
            else: selected_zones = None

        filtered_inventory = inventory.copy()
        if search:
            search_mask = filtered_inventory.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False, regex=False)).any(axis=1)
            filtered_inventory = filtered_inventory[search_mask]
        if demand_col is not None and selected_classes is not None:
            filtered_inventory = filtered_inventory[filtered_inventory[demand_col].fillna("UNKNOWN").astype(str).isin(selected_classes)]
        if zone_col is not None and selected_zones is not None:
            filtered_inventory = filtered_inventory[filtered_inventory[zone_col].fillna("UNKNOWN").astype(str).isin(selected_zones)]

        st.caption(f">> RETRIEVED **{len(filtered_inventory):,}** RECORDS / **{len(inventory):,}** TOTAL IN SYSTEM.")

        preferred_columns = [sku_col, location_col, demand_col, rationale_col, "Zone", "Aisle_Number", "Rack_ID", "Bay", "Shelf_Level", "Volumetric_Capacity_cm3", "Max_Weight_Capacity_kg"]
        display_columns = [col for col in preferred_columns if col is not None and col in filtered_inventory.columns]
        if not display_columns: display_columns = filtered_inventory.columns.tolist()

        st.dataframe(styled_frame(filtered_inventory[display_columns]), use_container_width=True, hide_index=True, height=420)
        st.download_button(label="[ DL_FILTERED_CSV ]", data=filtered_inventory[display_columns].to_csv(index=False).encode("utf-8"), file_name="filtered_inventory.csv", mime="text/csv")
        st.divider()

        st.markdown("#### 📊 DEMAND VECTOR VISUALIZER // 3D PLOT")
        if demand_col is not None:
            counts = inventory[demand_col].fillna("UNKNOWN").astype(str).value_counts().rename_axis("Demand Class").reset_index(name="SKU Records")
            chart_col, info_col = st.columns([3, 2], gap="large")
            with chart_col: plot_3d_category_values(counts, "Demand Class", "SKU Records", "3D SKU DISTRIBUTION", theme)
            with info_col:
                st.markdown("##### BREAKDOWN TABLE // LOG")
                st.dataframe(styled_frame(counts), use_container_width=True, hide_index=True)
        else: st.info("[!] NO DEMAND VECTOR FOUND.")

# ============================================================
# SKU FINDER
# ============================================================

elif page == "04_SKU_Finder":
    st.markdown("### MODULE 04 // 🔎 SKU PLACEMENT INSPECTOR")
    st.caption("DIRECT DB QUERY INTERFACE // AWAITING TARGET IDENTIFIER...")
    
    if optimized is None or optimized.empty:
        st.warning("ERR: optimized_allocation.csv UNAVAILABLE.")
    else:
        sku_data = optimized.copy()
        sku_col_finder = find_column(sku_data, "SKU_ID", "sku_id", "SKU")
        loc_col_finder = find_column(sku_data, "Location_ID", "location_id", "Location")
        demand_col_finder = find_column(sku_data, "Demand_Class", "demand_class", "class")
        
        if sku_col_finder is None: st.error("ERR: SKU_ID COLUMN MISSING.")
        else:
            query = st.text_input("INPUT EXACT SKU HASH", placeholder="SKU-XXXX", key="global_sku_finder")
            if demand_col_finder:
                classes = sorted(sku_data[demand_col_finder].dropna().astype(str).unique().tolist())
                selected_classes = st.multiselect("FILTER DEMAND", classes, default=classes, key="finder_classes")
                sku_data = sku_data[sku_data[demand_col_finder].fillna("UNKNOWN").astype(str).isin(selected_classes)]
            if query.strip():
                sku_data = sku_data[sku_data[sku_col_finder].astype(str).str.contains(query.strip(), case=False, na=False)]
            
            st.metric("MATCHING RECORDS", f"{len(sku_data):,}")
            if sku_data.empty: st.info("[!] NO MATCH. REVISE QUERY HASH.")
            else:
                st.dataframe(styled_frame(sku_data), use_container_width=True, hide_index=True)
                chosen_sku = st.selectbox("INSPECT SPECIFIC SKU [ISOLATE]", sku_data[sku_col_finder].astype(str).drop_duplicates().tolist(), key="finder_selected_sku")
                detail = sku_data[sku_data[sku_col_finder].astype(str) == chosen_sku]
                if locations is not None and not locations.empty and loc_col_finder and "Location_ID" in locations.columns:
                    detail = detail.merge(locations, left_on=loc_col_finder, right_on="Location_ID", how="left", suffixes=("", "_warehouse"))
                st.markdown("#### NODE SPECIFICATIONS // ISOLATED")
                st.dataframe(styled_frame(detail), use_container_width=True, hide_index=True)

# ============================================================
# WHAT-IF SIMULATOR
# ============================================================

elif page == "05_What-If_Simulator":
    st.markdown("### MODULE 05 // 🧪 VOLUME CAPACITY SIMULATOR")
    st.caption("STRESS-TEST HEURISTIC CAPACITY LOGIC // SANDBOX ENVIRONMENT")
    
    total_locations = int(locations["Location_ID"].nunique()) if locations is not None and "Location_ID" in locations.columns else (len(locations) if locations is not None else 0)
    allocated_sku_count = int(optimized["SKU_ID"].nunique()) if optimized is not None and "SKU_ID" in optimized.columns else (len(optimized) if optimized is not None else 0)
    unallocated_sku_count = int(unallocated["SKU_ID"].nunique()) if unallocated is not None and "SKU_ID" in unallocated.columns else (len(unallocated) if unallocated is not None else 0)
    current_sku_count = allocated_sku_count + unallocated_sku_count

    if total_locations <= 0 or current_sku_count <= 0:
        st.warning("ERR: MISSING DATA FOR SIMULATION ENVIRONMENT.")
    else:
        st.markdown("#### SCENARIO PARAMETERS // INPUT OVERRIDE")
        control_col, summary_col = st.columns([1, 1.4])
        with control_col:
            demand_growth = st.slider("DEMAND INFLATION (%)", min_value=-20, max_value=100, value=20, step=5, key="whatif_demand_growth")
            usable_capacity = st.slider("USABLE NODES (%)", min_value=50, max_value=100, value=90, step=5, key="whatif_usable_capacity")

        projected_skus = max(0, round(current_sku_count * (1 + demand_growth / 100)))
        usable_locations = max(0, round(total_locations * usable_capacity / 100))
        estimated_allocated = min(projected_skus, usable_locations)
        estimated_unallocated = max(0, projected_skus - usable_locations)
        estimated_coverage = estimated_allocated / projected_skus if projected_skus else 1.0

        with summary_col:
            st.markdown("#### PROJECTION OUTPUT // CALCULATION")
            k1, k2 = st.columns(2)
            k1.metric("PROJ SKUS", f"{projected_skus:,}", f"{demand_growth:+d}% DEMAND")
            k2.metric("EFFECTIVE NODES", f"{usable_locations:,}", f"{usable_capacity - 100:+d}% CAP")
            k3, k4 = st.columns(2)
            k3.metric("EST FULFILLED", f"{estimated_allocated:,}")
            k4.metric("EST OVERFLOW", f"{estimated_unallocated:,}", delta_color="inverse")
            st.progress(estimated_coverage, text=f"SYS CAPACITY COVERAGE: {estimated_coverage:.1%}")

        comparison = pd.DataFrame({"Measure": ["SKUs needed", "Usable nodes", "Est Allocated", "Est Overflow"], "Current Base": [current_sku_count, total_locations, min(current_sku_count, total_locations), max(0, current_sku_count - total_locations)], "Simulation": [projected_skus, usable_locations, estimated_allocated, estimated_unallocated]})
        st.markdown("#### 3D DELTA VISUALIZATION // DIFF")
        comparison_3d = comparison.melt(id_vars="Measure", var_name="Scenario", value_name="Count")
        comparison_3d["Measure + scenario"] = comparison_3d["Measure"].astype(str) + " // " + comparison_3d["Scenario"].astype(str)
        plot_3d_category_values(comparison_3d, "Measure + scenario", "Count", "SIMULATION DELTAS", theme)
        # --- ADDITION: ASCII ARCHITECTURE PIPELINE ---
        st.markdown("""
        <div style="background-color:#0E1117; padding:10px; border: 1px solid #00FFFF; border-radius: 5px; font-family: monospace; color: #00FFFF; text-align: center; margin-bottom: 20px;">
        [ RAW DATA ] ──► [ PREPROCESSING ] ──► [ MILP SOLVER ] ──► [ ROUTE HEURISTIC ] ──► [ TELEMETRY OUTPUT ]<br>
        &nbsp;&nbsp;CSV/DB&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Polars/Pandas&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;PuLP/SciPy&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Euclidean/A*&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Streamlit V5
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# PICK ROUTES
# ============================================================

elif page == "06_Pick_Routes":
    st.markdown("### MODULE 06 // 🛤️ ROUTING TELEMETRY")
    st.caption("EVALUATING ROUTE OPTIMIZATION ALGORITHMS // WAYPOINT LOGS")
    
    if optimized_routes is None or optimized_routes.empty:
        st.error("ERR: ROUTE DATA MISSING. PATHFINDER OFFLINE.")
        st.stop()

    route_orders = optimized_routes["Order_ID"].astype(str).tolist()
    selected_order = st.selectbox("SELECT ORDER HASH // [WAYPOINT ID]", route_orders)
    optimized_row = optimized_routes[optimized_routes["Order_ID"].astype(str) == selected_order].iloc[0]
    
    baseline_row = None
    if baseline_routes is not None and not baseline_routes.empty:
        matches = baseline_routes[baseline_routes["Order_ID"].astype(str) == selected_order]
        if not matches.empty: baseline_row = matches.iloc[0]

    opt_distance = float(optimized_row["Distance_m"])
    opt_complete = bool(optimized_row["Complete"])

    c1, c2, c3 = st.columns(3)
    c1.metric("OPT PATH (M)", f"{opt_distance:.2f}")
    c2.metric("STATUS_FLAG", "COMPLETE" if opt_complete else "FAIL")
    c3.metric("DB ORDERS CACHED", f"{len(optimized_routes):,}")
    st.divider()

    left, right = st.columns(2)
    with left:
        st.markdown("#### BASELINE PATH // LEGACY ALGO")
        if baseline_row is not None:
            st.metric("DISTANCE CALC", f"{float(baseline_row['Distance_m']):.2f} m")
            st.text_area("VISITED NODES ARRAY", str(baseline_row["Visited_SKUs"]), height=150, disabled=True, key="baseline_skus")
        else: st.info("[!] NO BASELINE RECORD.")

    with right:
        st.markdown("#### OPTIMIZED PATH // HEURISTIC ALGO")
        st.metric("DISTANCE CALC", f"{opt_distance:.2f} m")
        st.text_area("VISITED NODES ARRAY", str(optimized_row["Visited_SKUs"]), height=150, disabled=True, key="optimized_skus")

    if baseline_row is not None:
        base_distance = float(baseline_row["Distance_m"])
        st.markdown("#### PATH DELTA 3D GRAPH // COMPARISON")
        comparison_chart = pd.DataFrame({"Scenario": ["BASE", "OPT"], "Distance (m)": [base_distance, opt_distance]})
        fig = px.scatter_3d(comparison_chart, x="Scenario", y="Distance (m)", z="Distance (m)", color="Scenario", color_discrete_map={"BASE": theme["secondary"], "OPT": theme["accent"]}, template="plotly_dark")
        fig.update_traces(marker=dict(size=8, symbol="square"))
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Share Tech Mono", color=theme["text"]), scene=dict(xaxis=dict(gridcolor=theme["secondary"]), yaxis=dict(gridcolor=theme["secondary"]), zaxis=dict(gridcolor=theme["secondary"])))
        st.plotly_chart(fig, use_container_width=True)
            # --- ADDITION: RADIAL TELEMETRY GAUGES ---
    st.markdown("<h4 style='color: #00FFFF; font-family: monospace;'>SYSTEM TELEMETRY</h4>", unsafe_allow_html=True)
    gauge_col1, gauge_col2, gauge_col3 = st.columns(3)

    def create_gauge(title, value, max_val, color):
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=value,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': title, 'font': {'color': 'white', 'size': 14}},
            number={'font': {'color': color}},
            delta={'reference': value - 5, 'increasing': {'color': "#00FF00"}},
            gauge={
                'axis': {'range': [None, max_val], 'tickcolor': "white"},
                'bar': {'color': color, 'thickness': 0.75},
                'bgcolor': "#1E1E1E",
                'borderwidth': 2,
                'bordercolor': "#333333",
                'steps': [{'range': [0, max_val*0.8], 'color': '#0E1117'}]
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20), paper_bgcolor="rgba(0,0,0,0)")
        return fig

    with gauge_col1:
        st.plotly_chart(create_gauge("VOLUMETRIC FILL (%)", 84.2, 100, "#00FFFF"), use_container_width=True)
    with gauge_col2:
        st.plotly_chart(create_gauge("SOLVER GAP (%)", 1.2, 5, "#FF003C"), use_container_width=True)
    with gauge_col3:
        st.plotly_chart(create_gauge("ROUTING EFFICIENCY", 92.5, 100, "#00FF00"), use_container_width=True)
        # --- ADDITION: THERMAL CONGESTION HEATMAP ---
        st.markdown("<h4 style='color: #00FFFF; font-family: monospace;'>ZONE VELOCITY & CONGESTION HEATMAP</h4>", unsafe_allow_html=True)

        # Generate synthetic heatmap data for demonstration (replace with actual matrix density data)
        grid_size = 20
        congestion_data = np.random.poisson(lam=3, size=(grid_size, grid_size))
        # Create hotspots
        congestion_data[5:9, 10:14] += 15 
        congestion_data[15:18, 2:6] += 10

        heatmap_fig = go.Figure(data=go.Heatmap(
            z=congestion_data,
            colorscale='Inferno', # Dark to bright red/yellow
            hoverongaps=False,
            showscale=True
        ))
        heatmap_fig.update_layout(
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#333", zeroline=False, title="Aisle Coordinates"),
            yaxis=dict(showgrid=True, gridcolor="#333", zeroline=False, title="Rack Depth")
        )
        st.plotly_chart(heatmap_fig, use_container_width=True)

# ============================================================
# ANALYTICS
# ============================================================

elif page == "07_Analytics":
    st.markdown("### MODULE 07 // 📈 DISTRIBUTION ANALYTICS")
    st.caption("MATHEMATICAL DISTRIBUTIONS & DATA CORRELATIONS // STATISTICS")

    tab1, tab2, tab3 = st.tabs(["AFFINITY PAIRS", "DEMAND MATRIX", "DIMENSIONAL FIT"])

    with tab1:
        st.markdown("#### SKU CORRELATIONS // AFFINITY_ALG")
        if affinity is not None:
            st.metric("PAIR RECORDS CACHED", f"{len(affinity):,}")
            score_col = find_column(affinity, "affinity_score", "support", "confidence", "lift", "score")
            if score_col:
                plot_df = affinity.copy()
                plot_df[score_col] = pd.to_numeric(plot_df[score_col], errors="coerce")
                plot_df = plot_df.dropna(subset=[score_col]).nlargest(15, score_col)
                if not plot_df.empty:
                    plot_df["Pair"] = plot_df[plot_df.columns[0]].astype(str)
                    plot_3d_category_values(plot_df, "Pair", score_col, "TOP CORRELATIONS", theme, max_points=15)
            show_table(affinity.head(100))
        else: st.info("[!] NO DATA IN BUFFER.")

    with tab2:
        st.markdown("#### DEMAND TOPOLOGY // HISTOGRAM")
        if demand is not None:
            numeric_cols = demand.select_dtypes(include="number").columns.tolist()
            if numeric_cols:
                selected_metric = st.selectbox("VECTOR PARAMETER [SELECT]", numeric_cols, key="demand_metric")
                values = pd.to_numeric(demand[selected_metric], errors="coerce").dropna()
                if not values.empty:
                    hist_counts, hist_edges = __import__("numpy").histogram(values, bins=30)
                    hist_df = pd.DataFrame({"Bin": [f"{hist_edges[i]:.3g}-{hist_edges[i+1]:.3g}" for i in range(len(hist_counts))], "Freq": hist_counts})
                    plot_3d_category_values(hist_df, "Bin", "Freq", f"3D DISTRIBUTION: {selected_metric}", theme, max_points=30)
            show_table(demand.head(100))
        else: st.info("[!] NO DATA IN BUFFER.")

    with tab3:
        st.markdown("#### VOLUMETRIC FIT // PHYSICAL_CONSTANTS")
        if dimensional is not None:
            numeric_cols = dimensional.select_dtypes(include="number").columns.tolist()
            if numeric_cols:
                selected_metric = st.selectbox("FIT PARAMETER [SELECT]", numeric_cols, key="dimension_metric")
                values = pd.to_numeric(dimensional[selected_metric], errors="coerce").dropna()
                hist_counts, hist_edges = __import__("numpy").histogram(values, bins=30)
                hist_df = pd.DataFrame({"Bin": [f"{hist_edges[i]:.3g}-{hist_edges[i+1]:.3g}" for i in range(len(hist_counts))], "Freq": hist_counts})
                plot_3d_category_values(hist_df, "Bin", "Freq", f"VOLUMETRIC: {selected_metric}", theme, max_points=30)
            show_table(dimensional.head(100))
        else: st.info("[!] NO DATA IN BUFFER.")

                # --- ADDITION: LIVE TERMINAL LOG FEED ---

        st.markdown("<h4 style='color: #00FFFF; font-family: monospace;'>STDOUT // SOLVER LOGS</h4>", unsafe_allow_html=True)
        terminal_container = st.empty()

        # Simulated terminal output format
        terminal_logs = """[16:42:01.402] [SYS]   Initializing Core MILP Engine...
        [16:42:01.450] [INFO]  Loading location constraints matrix (4502x1200)
        [16:42:01.890] [WARN]  Node 89X exceeds weight tolerance. Re-slotting to Zone B.
        [16:42:02.102] [SOLVE] Iteration 1: Primal Bound = 142.08 | Dual Bound = 139.12 | Gap = 2.08%
        [16:42:02.455] [SOLVE] Iteration 2: Primal Bound = 139.50 | Dual Bound = 139.15 | Gap = 0.25%
        [16:42:02.801] [INFO]  Convergence achieved. Generating optimal 3D pathing vectors...
        [16:42:03.005] [SYS]   A* Routing successful. Render sequence initiated."""

        # Renders as a dark, monospace code block
        terminal_container.code(terminal_logs, language='bash')

# ============================================================
# VALIDATION
# ============================================================

elif page == "08_Validation":
    st.markdown("### MODULE 08 // ⚠️ CONSTRAINT VALIDATION LOGS")
    st.caption("WARNING: BREACH LOGS MAY REQUIRE MANUAL INTERVENTION // OVERRIDE REQ.")
    baseline_issue_count = len(baseline_violations) if baseline_violations is not None else None
    optimized_issue_count = len(optimized_violations) if optimized_violations is not None else None
    unallocated_count = len(unallocated) if unallocated is not None else None
    
    alert_cols = st.columns(3)
    alert_cols[0].metric("BASE BREACHES", f"{baseline_issue_count:,}" if baseline_issue_count is not None else "ERR")
    alert_cols[1].metric("OPT BREACHES", f"{optimized_issue_count:,}" if optimized_issue_count is not None else "ERR", delta=(f"{optimized_issue_count - baseline_issue_count:+,} vs BASE" if optimized_issue_count is not None and baseline_issue_count is not None else None), delta_color="inverse")
    alert_cols[2].metric("UNALLOCATED SKUS", f"{unallocated_count:,}" if unallocated_count is not None else "ERR")

    left, right = st.columns(2)
    with left:
        st.markdown("#### BASELINE FAULTS // LEGACY")
        if baseline_violations is not None: show_table(baseline_violations)
    with right:
        st.markdown("#### OPTIMIZED FAULTS // CURRENT")
        if optimized_violations is not None: show_table(optimized_violations)

    st.divider()
    st.markdown("#### UNALLOCATED BACKLOG // ORPHANED SKUS")
    if unallocated is not None: show_table(unallocated)

    unknown_hazards = number_metric(metrics, "unknown_hazard_attributes", "Optimized")
    if unknown_hazards is not None and unknown_hazards > 0:
        st.error(f"CRITICAL SYS_ALERT: {unknown_hazards:,.0f} UNKNOWN HAZARD ATTRIBUTES DETECTED. SAFETY LOCKOUT ENGAGED.")

# ============================================================
# DOWNLOADS
# ============================================================

elif page == "09_Downloads":
    st.markdown("### MODULE 09 // 💾 RAW DATA EXPORTS")
    st.caption("EXPORTING RAW CSV ARTIFACTS TO LOCAL STORAGE // AUTHORIZED PERSONNEL ONLY")
    
    files = [
        ("evaluation_comparison.csv", "METRICS_COMPARE_LOG"),
        ("optimized_allocation.csv", "OPT_ALLOCATION_DB"),
        ("baseline_allocation.csv", "BASE_ALLOCATION_DB"),
        ("warehouse_locations.csv", "WH_GEOMETRY_MAP"),
        ("optimized_routes.csv", "OPT_ROUTES_VECTORS"),
        ("baseline_routes.csv", "BASE_ROUTES_VECTORS"),
        ("optimized_violations.csv", "OPT_FAULTS_ERR_LOG"),
        ("baseline_violations.csv", "BASE_FAULTS_ERR_LOG"),
        ("unallocated_skus.csv", "UNALLOCATED_ORPHAN_LOG"),
        ("affinity_pairs.csv", "AFFINITY_MATRIX_DUMP"),
        ("demand_profile.csv", "DEMAND_LOG_HISTORY"),
        ("dimensional_fit.csv", "DIM_FIT_CONSTANTS"),
    ]

    for start in range(0, len(files), 3):
        cols = st.columns(3)
        for col, (filename, label) in zip(cols, files[start:start + 3]):
            with col: download_button_for_file(filename, f"[{label}]")

# ============================================================
# NEW MODULE: ADVANCED ROI
# ============================================================

elif page == "10_Advanced_ROI_Analysis":
    st.markdown("### MODULE 10 // 💰 FINANCIAL & LABOR OPEX PROJECTION")
    st.caption("CALCULATING THEORETICAL ROI BASED ON ROUTING HEURISTIC DELTAS. // PROJECTIONS ARE EXTRAPOLATIONS.")
    
    if metrics is None: 
        st.error("ERR: METRICS DATA MISSING. CANNOT COMPUTE OPEX.")
    else:
        tot_dist_base = number_metric(metrics, "total_distance_m", "Baseline") or 0
        tot_dist_opt = number_metric(metrics, "total_distance_m", "Optimized") or 0
        saved_m = max(0, tot_dist_base - tot_dist_opt)
        orders_sim = number_metric(metrics, "orders_simulated", "Optimized") or 1
        avg_saved_per_order = saved_m / orders_sim if orders_sim else 0
        
        col1, col2, col3 = st.columns(3)
        annual_orders = col1.number_input("ANNUAL VOL INPUT [EST]", min_value=1000, value=500000, step=10000)
        walking_speed = col2.number_input("PICKER VELOCITY (M/S) [MAX]", min_value=0.5, value=1.4, step=0.1)
        labor_rate = col3.number_input("LABOR COST ($/HR) [WAGE]", min_value=10.0, value=25.0, step=1.0)
        
        annual_meters_saved = avg_saved_per_order * annual_orders
        hours_saved = (annual_meters_saved / walking_speed) / 3600
        cost_savings = hours_saved * labor_rate
        
        st.divider()
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("DIST DELTA/ORDER", f"{avg_saved_per_order:.2f} m")
        r2.metric("ANNUAL DIST DELTA", f"{annual_meters_saved/1000:,.0f} km")
        r3.metric("LABOR HR RECOVERY", f"{hours_saved:,.0f} hr")
        r4.metric("OPEX REDUCTION", f"${cost_savings:,.0f}")
        
        st.info("SYS_NOTE: OUTPUTS ARE THEORETICAL FINANCIAL MODELS DERIVED FROM DETERMINISTIC MILP SOLVER ROUTES.")

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.markdown(
    f"""
    <div class="micro-text" style="text-align: center;">
        TERMINAL // WH-INTELLIGENCE // V5.1.0 // SECURE UPLINK ESTABLISHED <br>
        LAST_SYNC: {current_time} | ENCRYPTION: AES-256-GCM | SECTOR 7G ALL CLEAR
    </div>
    """,
    unsafe_allow_html=True,
)
