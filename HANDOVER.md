# SnakeCharmers — Handover Notes

## Project status

The repository contains an end-to-end warehouse-slotting prototype: Olist data preparation, demand profiling, Ridge next-week demand forecasting, affinity analysis, synthetic warehouse generation, baseline allocation, greedy optimization, route simulation, evaluation, saved reports, and a Streamlit dashboard.

**Current branch:** `Magnus`

**Important:** The latest GitHub commits for validation reporting and missing-data metrics were made directly on this branch. They still need to be pulled and tested in the recipient's local environment before this handover can be called fully verified.

## Run and verify (Windows PowerShell)

Open PowerShell in the repository root:

```powershell
git checkout Magnus
git pull origin Magnus
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m scripts.run_pipeline
.venv\Scripts\python.exe scripts\validate_saved_layouts.py
.venv\Scripts\python.exe -m streamlit run dashboard.py
```

The Streamlit command prints a local URL; open it in a browser. Stop the server with Ctrl+C.

If the existing virtual environment is absent, create one and install requirements:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The pipeline requires the Olist source CSVs in `data/raw/`. If they are missing, follow the dataset instructions in README.md and run the preparation/download scripts available in `scripts/`. Do not commit raw data or generated local outputs unless the project owner explicitly decides otherwise.

## Acceptance checklist

- [ ] Latest `Magnus` branch pulled successfully.
- [ ] `pytest -q` passes on the recipient's machine.
- [ ] Complete pipeline exits successfully and writes reports/CSVs.
- [ ] Saved-layout validator runs successfully.
- [ ] Dashboard opens and displays baseline vs optimized results.
- [ ] Dashboard distinguishes confirmed violations from unverified checks.
- [ ] Both allocation files are compared on the same active assortment.
- [ ] Final validation report and ML/optimization reports have been reviewed.
- [ ] Any result quoted in a presentation is copied from the latest local run, not an older run.

## What the metrics mean

- **Active assortment coverage**: allocated SKUs divided by the configured active assortment. A prior local run reported 100% coverage for the selected 200-SKU assortment.
- **Catalog-wide allocation coverage**: allocated layout rows divided by the full SKU profile; it is expected to be much lower when only a limited assortment is selected.
- **Whole-warehouse utilization**: modeled SKU volume divided by total generated warehouse capacity.
- **Allocated-bin utilization**: modeled SKU volume divided by the capacity of bins used by the layout.
- **Confirmed violations** are checks explicitly marked `VIOLATION`.
- **Unverified checks** indicate missing/unknown data or checks that cannot be established from available inputs. They are not confirmed violations, but they also are not proof of safety.

A previous local run (before the most recent missing-attribute metric additions) reported 24 passing tests, 500 simulated orders, 494 complete routes for both strategies, and route distance decreasing from 13,191.2 m (baseline) to 11,591.6 m (optimized), about 12.13%. Treat these as historical results only; rerun the current branch and use the newly generated report for final claims.

## Known limitations / do not overclaim

1. **Synthetic warehouse:** rack layout, dimensions, capacity ratings, and coordinates are configuration-driven simulation inputs, not a surveyed facility.
2. **Inventory is unknown:** Olist does not provide a current stock snapshot. Representative-stock assumptions must be clearly labeled.
3. **Hazard and handling data are unknown:** do not infer hazard classifications from category names. The validator/dashboard must continue to show unknown checks as unverified.
4. **Demand proxy:** Olist order-item lines are used as demand observations; they are not a measured current inventory quantity.
5. **Heuristic optimization:** the greedy reassignment is feasible under modeled constraints but does not guarantee a global optimum.
6. **Estimated travel:** route distance/time are simulated estimates, not measured warehouse results.
7. **Utilization:** low modeled volume utilization may reflect representative-stock assumptions and active-assortment scope; do not tune the warehouse size or objective merely to make the percentage look better without a documented requirement.

For operational deployment, obtain a real warehouse map and capacity ratings, current stock counts, product handling/hazard metadata, and a validated walkable route graph. Have warehouse safety requirements reviewed by a qualified owner before using generated assignments operationally.

## Useful locations

- `config/`: warehouse and simulation configuration.
- `src/`: demand, affinity, feasibility, allocation, optimization, routing, and evaluation logic.
- `scripts/run_pipeline.py`: full pipeline entry point.
- `scripts/validate_saved_layouts.py`: revalidate saved layouts.
- `tests/`: automated checks.
- `data/processed/`: generated local CSVs.
- `reports/`: generated audit, forecasting, optimization, and validation reports.
- `dashboard.py`: Streamlit dashboard.
