"""Interactive dashboard for Smart Warehouse Slotting & Optimization."""
from itertools import permutations
from pathlib import Path
import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed"
THEMES = {
    "CYBER TERMINAL": {"background":"#050505","panel":"#0a0a0a","text":"#00ff41","accent":"#00ffff","secondary":"#333333","success":"#00ff41","danger":"#ff003c"},
    "DARK MATTER": {"background":"#0b0f19","panel":"#111827","text":"#e2e8f0","accent":"#38bdf8","secondary":"#334155","success":"#34d399","danger":"#f43f5e"},
}

st.set_page_config(page_title="Warehouse Intelligence Terminal", page_icon="🖥️", layout="wide")
with st.sidebar:
    selected_theme = st.selectbox("INTERFACE THEME", list(THEMES))
theme = THEMES[selected_theme]
st.markdown(f"""<style>
html,body,[class*="css"]{{background:{theme['background']};color:{theme['text']};background-image:linear-gradient({theme['secondary']}55 1px,transparent 1px),linear-gradient(90deg,{theme['secondary']}55 1px,transparent 1px);background-size:30px 30px}}
[data-testid="stMetric"]{{background:{theme['panel']};border:1px solid {theme['secondary']};border-top:3px solid {theme['accent']};padding:1rem}}
[data-testid="stMetricValue"]{{color:{theme['accent']} !important;font-family:monospace !important}}
.hero{{padding:1.7rem;border:1px solid {theme['accent']};border-left:7px solid {theme['accent']};background:{theme['panel']}}}
.hero h1{{color:{theme['accent']} !important;margin:0}}
</style>""", unsafe_allow_html=True)

@st.cache_data
def load_csv(name):
    p = DATA / name
    if not p.exists(): return None
    try: return pd.read_csv(p)
    except Exception: return None

def col(df, *names):
    if df is None or df.empty: return None
    norm = {str(c).lower().replace(" ", "_"): c for c in df.columns}
    for n in names:
        k = n.lower().replace(" ", "_")
        if k in norm: return norm[k]
    for n in names:
        k = n.lower().replace(" ", "_")
        for nk, original in norm.items():
            if k in nk: return original
    return None

def metric(df, name, scenario="Optimized"):
    mc, vc = col(df,"Metric"), col(df,scenario)
    if mc is None or vc is None: return None
    m = df[df[mc].astype(str).str.lower() == name.lower()]
    return None if m.empty else pd.to_numeric(m.iloc[0][vc], errors="coerce")

def table(df, msg="[!] NO DATA AVAILABLE"):
    st.dataframe(df, use_container_width=True, hide_index=True) if df is not None and not df.empty else st.info(msg)

def make_dimensional_fit(allocation, skus, locations):
    """Check each assigned SKU against its assigned bin in all permitted orientations."""
    if any(x is None or x.empty for x in (allocation, skus, locations)): return None
    ps={"SKU_ID","Width_cm","Height_cm","Depth_cm"}; ls={"Location_ID","Bin_Width_cm","Bin_Height_cm","Bin_Depth_cm"}
    if not ps.issubset(skus.columns) or not ls.issubset(locations.columns): return None
    d=allocation.merge(skus[list(ps)],on="SKU_ID",how="left").merge(locations[list(ls)],on="Location_ID",how="left")
    def fits(r):
        p=[pd.to_numeric(r[x],errors="coerce") for x in ("Width_cm","Height_cm","Depth_cm")]
        b=[pd.to_numeric(r[x],errors="coerce") for x in ("Bin_Width_cm","Bin_Height_cm","Bin_Depth_cm")]
        if any(pd.isna(x) or x<=0 for x in p+b): return False
        return any(all(a<=z for a,z in zip(o,b)) for o in permutations(p))
    d["Fits_Assigned_Bin"]=d.apply(fits,axis=1)
    d["Product_Volume_cm3"]=d[["Width_cm","Height_cm","Depth_cm"]].prod(axis=1)
    d["Bin_Volume_cm3"]=d[["Bin_Width_cm","Bin_Height_cm","Bin_Depth_cm"]].prod(axis=1)
    d["Volume_Utilization"]=d["Product_Volume_cm3"]/d["Bin_Volume_cm3"]
    return d

metrics=load_csv("evaluation_comparison.csv")
optimized=load_csv("optimized_allocation.csv"); baseline=load_csv("baseline_allocation.csv")
locations=load_csv("warehouse_locations.csv"); skus=load_csv("sku_master.csv")
routes=load_csv("optimized_routes.csv"); base_routes=load_csv("baseline_routes.csv")
affinity=load_csv("affinity_pairs.csv"); demand=load_csv("demand_profile.csv")
unallocated=load_csv("unallocated_skus.csv"); reasons=load_csv("unallocated_reason_summary.csv")
bv=load_csv("baseline_violations.csv"); ov=load_csv("optimized_violations.csv")
dimensional = load_csv("dimensional_fit.csv")
if dimensional is None:
    dimensional = make_dimensional_fit(optimized, skus, locations)

if metrics is None:
    st.error("evaluation_comparison.csv is missing. Run: python run_pipeline.py")
    st.stop()

# Display the baseline-versus-optimized metrics already loaded above.
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
