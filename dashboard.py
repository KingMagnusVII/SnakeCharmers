"""Streamlit dashboard backed only by generated pipeline artifacts."""
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'/'processed'
st.set_page_config(page_title='Smart Warehouse Slotting', layout='wide'); st.title('Smart Warehouse Slotting & Optimization')
comparison=DATA/'evaluation_comparison.csv'
if not comparison.exists(): st.error('Run `python scripts/run_pipeline.py` first; generated outputs are missing.'); st.stop()
metrics=pd.read_csv(comparison); st.caption('Synthetic warehouse geometry and representative-stock assumptions are simulation inputs, not measured safety data.')
st.subheader('Baseline versus optimized'); st.dataframe(metrics, use_container_width=True)
left,right=st.columns(2)
with left:
    st.subheader('Optimized allocation'); st.dataframe(pd.read_csv(DATA/'optimized_allocation.csv').head(100), use_container_width=True)
with right:
    st.subheader('Validation'); st.metric('Optimized violations', len(pd.read_csv(DATA/'optimized_violations.csv')))
st.subheader('Affinity pairs'); st.dataframe(pd.read_csv(DATA/'affinity_pairs.csv').head(50), use_container_width=True)
