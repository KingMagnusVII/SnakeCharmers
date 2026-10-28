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
dimensional=load_csv("dimensional_fit.csv") or make_dimensional_fit(optimized,skus,locations)

if metrics is None:
    st.error("evaluation_comparison.csv is missing. Run: python scripts/run_pipeline.py")
    st.stop()

st.sidebar.markdown("## 📟 TERMINAL ACCESS")
page=st.sidebar.radio("SYSTEM MODULES",["Overview","Warehouse","Slotting","SKU Finder","What-If","Routes","Analytics","Validation","Downloads","ROI"])
st.markdown(f"<div class='hero'><h1>WAREHOUSE OPTIMIZATION TERMINAL</h1><p>HEURISTIC SLOTTING // PATHFINDING // CAPACITY SIMULATION</p></div>",unsafe_allow_html=True)

if page=="Overview":
    st.markdown("### MODULE 01 // SYSTEM OVERVIEW")
    b=metric(metrics,"total_distance_m","Baseline"); o=metric(metrics,"total_distance_m")
    c=metric(metrics,"allocation_coverage"); u=metric(metrics,"whole_warehouse_utilization"); bu=metric(metrics,"allocated_bin_utilization")
    with st.expander("COMPARATIVE ANALYSIS // BASELINE VS OPTIMIZED"):
        a,z=st.columns(2); a.metric("BASELINE TOTAL DISTANCE",f"{b:,.2f} m" if b is not None else "N/A"); z.metric("OPTIMIZED TOTAL DISTANCE",f"{o:,.2f} m" if o is not None else "N/A",delta=f"{o-b:+,.2f} m" if b is not None and o is not None else None,delta_color="inverse")
    cs=st.columns(5); cs[0].metric("ORDERS",f"{metric(metrics,'orders_simulated') or 0:,.0f}"); cs[1].metric("COMPLETE",f"{metric(metrics,'complete_orders') or 0:,.0f}"); cs[2].metric("ALLOCATED SKUS",f"{len(optimized) if optimized is not None else 0:,}"); cs[3].metric("COVERAGE",f"{c*100:.2f}%" if c is not None else "N/A"); cs[4].metric("BIN UTIL",f"{bu*100:.2f}%" if bu is not None else "N/A")
    st.metric("WHOLE-WAREHOUSE UTILIZATION",f"{u*100:.2f}%" if u is not None else "N/A"); table(metrics)

elif page=="Warehouse":
    st.markdown("### MODULE 02 // SPATIAL DIGITAL TWIN")
    if locations is None: st.error("warehouse_locations.csv missing"); st.stop()
    d=locations.copy()
    if optimized is not None: d=d.merge(optimized[["Location_ID","SKU_ID","Demand_Class"]].drop_duplicates("Location_ID"),on="Location_ID",how="left")
    d["Status"]=d.SKU_ID.notna().map({True:"ALLOCATED",False:"VACANT"})
    status=st.multiselect("NODE STATUS",["ALLOCATED","VACANT"],default=["ALLOCATED","VACANT"]); d=d[d.Status.isin(status)]
    fig=px.scatter_3d(d,x="X_m",y="Y_m",z="Z_m",color="Status",hover_name="Location_ID",template="plotly_dark"); fig.update_layout(height=650); st.plotly_chart(fig,use_container_width=True); table(d)

elif page=="Slotting":
    st.markdown("### MODULE 03 // INVENTORY MATRIX")
    q=st.text_input("SEARCH SKU / LOCATION / RATIONALE"); d=optimized.copy() if optimized is not None else None
    if d is not None and q: d=d[d.astype(str).apply(lambda x:x.str.contains(q,case=False,na=False,regex=False)).any(axis=1)]
    table(d)

elif page=="SKU Finder":
    st.markdown("### MODULE 04 // SKU PLACEMENT INSPECTOR")
    q=st.text_input("SKU HASH"); d=optimized.copy() if optimized is not None else None
    if d is not None and q: d=d[d.SKU_ID.astype(str).str.contains(q,case=False,na=False)]
    table(d)

elif page=="What-If":
    st.markdown("### MODULE 05 // CAPACITY SIMULATOR")
    current=(len(optimized) if optimized is not None else 0)+(len(unallocated) if unallocated is not None else 0); nodes=len(locations) if locations is not None else 0
    growth=st.slider("DEMAND INFLATION (%)",-20,100,20,5); usable=st.slider("USABLE NODES (%)",50,100,90,5)
    need=round(current*(1+growth/100)); cap=round(nodes*usable/100); alloc=min(need,cap); overflow=max(0,need-cap)
    x=st.columns(4); x[0].metric("PROJECTED SKUS",f"{need:,}"); x[1].metric("USABLE NODES",f"{cap:,}"); x[2].metric("EST ALLOCATED",f"{alloc:,}"); x[3].metric("EST OVERFLOW",f"{overflow:,}"); st.progress(alloc/need if need else 1)

elif page=="Routes":
    st.markdown("### MODULE 06 // ROUTING TELEMETRY")
    if routes is None or routes.empty: st.warning("Route data missing")
    else:
        oid=st.selectbox("ORDER",routes.Order_ID.astype(str)); r=routes[routes.Order_ID.astype(str)==oid].iloc[0]; st.metric("OPTIMIZED DISTANCE",f"{r.Distance_m:.2f} m");
        if base_routes is not None:
            q=base_routes[base_routes.Order_ID.astype(str)==oid]
            if not q.empty: st.metric("BASELINE DISTANCE",f"{float(q.iloc[0].Distance_m):.2f} m")
        st.write(r.to_dict())

elif page=="Analytics":
    st.markdown("### MODULE 07 // DISTRIBUTION ANALYTICS")
    a,b,c=st.tabs(["AFFINITY PAIRS","DEMAND MATRIX","DIMENSIONAL FIT"])
    with a: table(affinity)
    with b: table(demand)
    with c:
        st.caption("Dimensional fit = whether the assigned SKU physically fits its assigned bin in at least one permitted orientation.")
        if dimensional is None: st.warning("No dimensional-fit data available. Run the pipeline after this dashboard update.")
        else:
            fits=int(dimensional.Fits_Assigned_Bin.sum()); total=len(dimensional); x=st.columns(3); x[0].metric("ASSIGNMENTS CHECKED",total); x[1].metric("PHYSICAL FITS",fits); x[2].metric("FIT RATE",f"{fits/total*100:.2f}%" if total else "N/A"); table(dimensional)

elif page=="Validation":
    st.markdown("### MODULE 08 // CONSTRAINT VALIDATION")
    st.caption("Confirmed violations and UNVERIFIED checks are shown separately. UNVERIFIED is not evidence of compliance.")
    def vc(df):
        if df is None or df.empty:return 0,0
        s=col(df,"Status")
        if s is None:return len(df),0
        v=df[s].astype(str).str.upper(); return int((v=="VIOLATION").sum()),int((v=="UNVERIFIED").sum())
    b1,b2=vc(bv); o1,o2=vc(ov); x=st.columns(4); x[0].metric("BASE VIOLATIONS",b1); x[1].metric("OPT VIOLATIONS",o1,delta=f"{o1-b1:+d}",delta_color="inverse"); x[2].metric("BASE UNVERIFIED",b2); x[3].metric("OPT UNVERIFIED",o2)
    st.markdown("#### UNALLOCATED SKU DIAGNOSIS"); table(reasons); table(unallocated)
    st.markdown("#### BASELINE CHECKS"); table(bv); st.markdown("#### OPTIMIZED CHECKS"); table(ov)

elif page=="Downloads":
    st.markdown("### MODULE 09 // DATA EXPORTS")
    for name in ["evaluation_comparison.csv","optimized_allocation.csv","baseline_allocation.csv","warehouse_locations.csv","optimized_routes.csv","baseline_routes.csv","baseline_violations.csv","optimized_violations.csv","unallocated_skus.csv","unallocated_reason_summary.csv","affinity_pairs.csv","demand_profile.csv","sku_master.csv"]:
        d=load_csv(name)
        if d is not None: st.download_button(f"EXPORT {name}",d.to_csv(index=False),file_name=name,mime="text/csv",key=f"dl_{name}")
    if dimensional is not None: st.download_button("EXPORT dimensional_fit.csv",dimensional.to_csv(index=False),file_name="dimensional_fit.csv",mime="text/csv",key="dl_dim")

elif page=="ROI":
    st.markdown("### MODULE 10 // THEORETICAL ROI")
    b=metric(metrics,"total_distance_m","Baseline") or 0; o=metric(metrics,"total_distance_m") or 0; n=metric(metrics,"orders_simulated") or 1
    annual=st.number_input("ANNUAL ORDERS",1000,5000000,500000,10000); speed=st.number_input("PICKER SPEED (M/S)",.5,5.,1.4,.1); rate=st.number_input("LABOR COST ($/HR)",10.,200.,25.,1.)
    saved=max(0,b-o); meters=saved/n*annual; hours=meters/speed/3600; cost=hours*rate
    x=st.columns(4); x[0].metric("DISTANCE SAVED/ORDER",f"{saved/n:.2f} m"); x[1].metric("ANNUAL DISTANCE",f"{meters/1000:,.0f} km"); x[2].metric("HOURS",f"{hours:,.0f}"); x[3].metric("THEORETICAL SAVING",f"${cost:,.0f}")
    st.info("ROI values are extrapolations from simulated route distance, not measured warehouse savings.")

st.divider(); st.caption(f"WH-INTELLIGENCE // LAST SYNC {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
