# SnakeCharmers — Smart Warehouse Slotting & Optimization

A reproducible prototype that uses Olist e-commerce order history to forecast demand, allocate a configurable active SKU assortment to a synthetic warehouse, optimize slotting heuristically, simulate picking routes, and compare results in a Streamlit dashboard.

## Quick start (Windows PowerShell)

Run commands from the repository root. The project has been tested locally by the maintainer with the existing `.venv`; fresh environments should install dependencies first.

```powershell
git checkout Magnus
git pull origin Magnus
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m scripts.run_pipeline
.venv\Scripts\python.exe scripts\validate_saved_layouts.py
.venv\Scripts\python.exe -m streamlit run dashboard.py
```

If setting up from scratch, create the virtual environment first:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Input data

The pipeline uses the public [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Raw files are not committed to Git. Download/prepare the data using the scripts in `scripts/` and follow any Kaggle access/credential requirements. The pipeline expects the raw CSV files in `data/raw/`.

**Data limitations that must remain explicit:**
- Olist order items do not supply a dependable explicit quantity field, so recorded order-item lines are used as a demand proxy.
- Olist does not supply a current inventory snapshot. `Inventory_Units` can remain unknown; any representative-stock fallback is a simulation assumption, not measured inventory.
- Olist does not supply dependable SKU hazard/handling classifications. Missing values remain unspecified and must not be treated as safety clearance.
- Warehouse locations, rack/bin dimensions, capacity values, and distances are synthetic configuration inputs, not surveyed warehouse data or engineering certification.

## Pipeline

1. Load and normalize Olist inputs.
2. Analyze SKU demand and data quality.
3. Forecast next-week SKU demand with a Ridge model.
4. Compute product affinity from order co-occurrence.
5. Generate synthetic warehouse locations.
6. Allocate the configured active assortment with a constraint-aware baseline.
7. Reassign feasible slots using demand priority, affinity, distance, and ergonomic heuristics.
8. Simulate baseline and optimized picking routes.
9. Evaluate route distance/time, coverage, utilization, and validation-data completeness.
10. Save reports and CSV outputs for the dashboard.

Configuration lives in `config/`. Source modules are in `src/`, runnable scripts in `scripts/`, and tests in `tests/`.

## Main outputs

Generated artifacts are written locally under `data/processed/` (typically ignored by Git). Reports are written under `reports/`, including:
- `data_foundation_audit.md`
- `eda_report.md`
- `ml_demand_report.md`
- `optimization_report.md`
- `unallocated_sku_diagnosis.md`
- `final_validation_report.md`

The dashboard reads the saved CSV outputs; run the pipeline first, then launch Streamlit.

## Interpreting metrics safely

- **Active assortment coverage** measures whether the selected assortment was allocated; it is not coverage of every SKU in the full catalog.
- **Catalog-wide allocation coverage** uses the full product profile as its denominator and can therefore be low when only a limited active assortment is modeled.
- **Whole-warehouse utilization** and **allocated-bin utilization** use different capacity denominators and should not be confused with allocation coverage.
- **Confirmed violations** and **UNVERIFIED checks** are separate. Unknown inventory, hazard, or handling attributes are not evidence that a layout is safe.
- The optimizer is a greedy heuristic, not a proof of global optimality. Simulated routes and estimated time are not measured warehouse performance.

See [HANDOVER.md](HANDOVER.md) for the final verification checklist, known limitations, and transfer instructions.
