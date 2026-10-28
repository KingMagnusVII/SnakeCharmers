<div align="center">

# 🐍 SnakeCharmers

### Smart Warehouse Slotting & Optimization

*Forecast demand. Slot smarter. Walk less.*

![Python](https://img.shields.io/badge/Python-3.15-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-3.x-150458?logo=pandas&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Ridge-F7931E?logo=scikitlearn&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-dashboard-FF4B4B?logo=streamlit&logoColor=white)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)

</div>

---

## Overview

SnakeCharmers is a **research and simulation prototype** for assigning products (SKUs) to locations in a synthetic warehouse and comparing estimated picking routes. It uses historical Brazilian Olist e-commerce order data; it does not connect to a live warehouse, stock system, or real-time order stream.

The intended workflow is:

1. Normalize the supported Olist source tables and profile historical demand.
2. Forecast next-week recorded order-line counts with a Ridge regression model.
3. Generate a synthetic warehouse layout and build a constrained baseline allocation.
4. Compare demand-ranked and order-coverage-first assortment strategies.
5. Reassign feasible slots with a greedy heuristic and bounded route-distance swap refinement.
6. Simulate routes, evaluate layouts, run a chronological inventory/picking holdout experiment, and write CSV/Markdown reports for analysis.

> [!CAUTION]
> **This is not a deployment-ready warehouse safety or inventory system.** Warehouse geometry is synthetic; Olist contains historical order lines, not current on-hand inventory; and dependable hazard/handling classifications are unavailable. A result with zero *known* violations is not proof of safety. Unknown checks must remain unverified.

## What is implemented

| Component | Current implementation |
|---|---|
| Demand profile | Historical recorded order lines, category context, and ABC classes |
| Demand forecast | scikit-learn Ridge regression predicting next-week recorded order-line counts |
| Baseline | Deterministic demand-ranked assortment and constrained allocation |
| Alternative assortment | Order-coverage-first candidate selection for comparison |
| Slotting heuristic | Greedy reassignment using forecast priority, depot distance, affinity, and ergonomic penalties |
| Refinement | Bounded feasible location swaps accepted when simulated route distance decreases |
| Validation | Reference, uniqueness, dimensional, load, ergonomic, compatibility, and data-completeness checks |
| Routing | Simplified route simulation over synthetic warehouse coordinates |
| Holdout experiment | Chronological train/test split; starting stock estimated from training-period demand, then later orders replayed |
| Dashboard | Streamlit interface intended to display generated results; see the current known issues below |

The slotting optimizer is a **heuristic**, not a trained machine-learning model and not a proof of global optimality. The separate *src/milp_assortment.py* file is an experimental MILP assortment selector; it is **not currently wired into the main pipeline**.

## Quick start

Commands below are for Windows PowerShell from the repository root. The project requirements and GitHub Actions workflow target Python 3.15.

    git checkout Magnus
    git pull origin Magnus
    py -3.15 -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m pytest -q

The raw Olist CSV files must be available in *data/raw/* before running the full pipeline. If they are missing, follow the data section below.

    .venv\Scripts\python.exe -m scripts.run_pipeline
    .venv\Scripts\python.exe scripts\validate_saved_layouts.py
    .venv\Scripts\python.exe -m streamlit run dashboard.py

Streamlit normally prints a local URL. Stop it with Ctrl+C.

> [!WARNING]
> The current Magnus snapshot has known execution blockers that need code fixes before the full run sequence can be considered verified: *scripts/run_pipeline.py* contains a duplicated refinement section that refers to *greedy* outside the helper where it is defined, and *dashboard.py* refers to an undefined *comparison* variable and uses a DataFrame in a boolean expression. The README does not treat the pipeline or dashboard as verified until those issues are fixed and rerun.

### Useful commands

| Task | Command |
|---|---|
| Download the Olist dataset | *python -m scripts.download_olist* |
| Prepare normalized data | *python -m scripts.prepare_data* |
| Run exploratory analysis | *python -m scripts.run_eda* |
| Run the full pipeline | *python -m scripts.run_pipeline* |
| Revalidate saved layouts without regenerating them | *python scripts/validate_saved_layouts.py* |
| Run tests | *python -m pytest -q* |
| Start the dashboard | *python -m streamlit run dashboard.py* |

Use the same Python interpreter for installing dependencies, running tests, running scripts, and launching Streamlit. If imports fail in a local environment, run from the repository root and prefer *python -m ...* commands.

## Input data: Olist

Source: [Olist Brazilian E-Commerce Public Dataset on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). It records Brazilian marketplace transactions from 2016–2018. The raw data is not intended to be committed to this repository.

The project reads three source tables:

| Source CSV | Fields used | Purpose |
|---|---|---|
| *olist_orders_dataset.csv* | *order_id*, *order_purchase_timestamp*, *order_status* | Order identity, timestamp, and configured status filter |
| *olist_order_items_dataset.csv* | *order_id*, *order_item_id*, *product_id*, *price*, *freight_value* | Order-to-product lines and retained transaction fields |
| *olist_products_dataset.csv* | *product_id*, *product_category_name*, *product_weight_g*, *product_length_cm*, *product_height_cm*, *product_width_cm* | SKU category, dimensions, and weight |

Other Olist tables are not currently used as model inputs. Do not describe customer, payment, review, seller, or geolocation fields as active features.

Kaggle downloads require an account, acceptance of dataset terms, and API credentials. Keep credentials such as *kaggle.json* private and out of Git.

### Important data assumptions

- Each recorded order-item row is treated as one demand-line observation. The dataset does not provide a reliable item quantity for this project, so this is **not a verified units-sold or stock measure**.
- The default demand status is *delivered*, configured by *demand_statuses*.
- Product dimensions are converted into centimeters and weight into kilograms. Length is represented as depth in the normalized schema.
- Missing or invalid physical metadata can exclude a SKU from feasible allocation.
- Hazard and handling attributes are not reliably available and must not be inferred from product category names.
- *representative_inventory_units* is a fallback assumption for modeled load checks, not an observed stock count.
- The holdout experiment estimates starting inventory from earlier recorded order-line history. Its stock values are simulated, not actual inventory.

## How the model and optimizer work

### Demand forecasting

*src/ml_demand.py* trains a scikit-learn *Ridge(alpha=1.0)* model when enough valid historical data is available. Its target is weekly recorded order-line count, transformed with *log1p* during fitting.

Features include:

- *Lag_1*: previous week's recorded line count.
- *Lag_4*: count four weeks earlier.
- *Rolling_4*: shifted mean over up to four prior weeks.
- *Historical_Mean*: expanding mean using prior weeks only.
- *Week_Index*: simple time trend.
- *Category*: normalized product category, one-hot encoded.

Numeric features are median-imputed and standardized; categories are imputed and one-hot encoded. Predictions are transformed back with *expm1* and clipped to non-negative values. If timestamps or training rows are insufficient, the forecast stage reports that it did not train and returns zero predictions.

The forecast is used as a **slotting priority signal**. It is not a real-time replenishment system, and a trained model alone does not establish forecast accuracy. Use a chronological held-out evaluation before claiming predictive performance.

### Slotting and route refinement

- The baseline and optimized layouts are compared using the same selected assortment for that comparison.
- The greedy heuristic prioritizes higher forecast-demand SKUs, then scores feasible candidate locations using depot distance, affinity with already placed SKUs, and an ergonomic penalty.
- SKU affinity is derived from products appearing in the same historical orders.
- A bounded swap search tests feasible location exchanges and accepts a swap only if the simulated route-distance objective improves.
- Baseline, greedy, and refined candidates are checked for known hard-constraint violations. The selection gate chooses the candidate with the lowest simulated route distance among those with no confirmed violations; the baseline can therefore win and an optimization improvement is not guaranteed.
- A separate order-coverage-first assortment comparison and a chronological inventory/picking holdout experiment are also generated by the pipeline.

The route model uses simplified synthetic geometry and assumptions. It is not a surveyed walkable path network, and estimated distances/times are not measured warehouse performance.

## Validation and interpreting results

The shared feasibility logic in *src/feasibility.py* checks modeled conditions including:

- SKU and location references, assignment uniqueness, and location uniqueness.
- Product dimensions and fit under permitted rotations.
- Bin, shelf, and rack load limits using available inventory or the configured fallback.
- Heavy-SKU shelf-level rules.
- Explicitly configured incompatibilities only; the code does not infer unknown hazards or handling requirements.
- Missing or invalid data that prevents a check from being established.

Validation statuses have distinct meanings:

| Status | Interpretation |
|---|---|
| *OK* | The check passed with the available data and modeled rule |
| *VIOLATION* | A configured constraint was confirmed to be violated |
| *UNVERIFIED* | Required information is missing or insufficient to establish the check |

**Do not describe “zero violations” as “safe” or “compliant” when checks remain unverified.** Olist does not provide current stock, dependable hazard classifications, or handling requirements.

### Metrics

Generated evaluation reports may include:

- **Order completion:** complete routes divided by the orders in the evaluated route sample. This can differ depending on whether zero-pick/source orders are included.
- **Route distance:** simulated distance over the selected route sample.
- **Estimated time:** distance divided by assumed walking speed plus assumed handling time.
- **Active-assortment coverage:** selected active SKUs assigned a location divided by the selected active assortment.
- **Catalog-wide allocation coverage:** allocated SKU rows relative to the broader SKU profile.
- **Warehouse/bin utilization:** modeled product volume relative to generated warehouse capacity or used-bin capacity.
- **Unverified checks:** checks that could not be established from available source data.

These measures are not interchangeable. In particular, allocation coverage does not mean orders can be fulfilled from available stock, and route distance from a pickable-order sample should not be compared directly with a source-order sample containing zero-pick orders.

### Where to find current results

Do **not** rely on fixed numbers copied into documentation as if they were current. Re-run the pipeline after resolving its known blocker, then use the generated files in *data/processed/* and *reports/*, including:

- *evaluation_comparison.csv*
- *assortment_strategy_comparison.csv*
- *source_order_routes.csv* and *source_order_routes_coverage_first.csv*
- *inventory_holdout_comparison.csv*
- *reports/optimization_report.md*
- *reports/final_validation_report.md*
- *reports/inventory_holdout_experiment.md*
- *reports/source_order_coverage_report.md*
- *reports/correctness_hardening_report.md*

Generated outputs may describe an older run. Check their timestamps and regenerate them before quoting results.

## Configuration

Main settings are in *config/simulation_config.json*; warehouse dimensions and capacities are defined in *config/warehouse_config.json*.

| Setting | Current configured value | Meaning |
|---|---:|---|
| *demand_statuses* | *["delivered"]* | Order statuses included in demand analysis |
| *max_active_skus* | *500* | Configured cap for the active assortment |
| *representative_inventory_units* | *1* | Fallback units for modeled stock/load checks |
| *allow_rotations* | *true* | Permit dimension permutations in fit checks |
| *ergonomics.heavy_sku_weight_kg* | *10* | Configured heavy-SKU threshold for validation |
| *ergonomics.max_shelf_level_for_heavy_skus* | *2* | Highest permitted shelf level for heavy SKUs |
| *incompatibility_rules.category_hazard_pairs* | *[]* | No category/hazard rules supplied by default |
| *incompatibility_rules.hazard_handling_pairs* | *[]* | No hazard/handling rules supplied by default |
| *abc_thresholds* | A: *0.8*, B: *0.95* | Cumulative demand-share cut-offs |
| *walking_speed_m_per_min* | *75* | Assumed walking speed |
| *pick_handling_seconds* | *12* | Assumed handling time per simulated order |
| *objective_weights.distance* | *1* | Depot-distance weight |
| *objective_weights.affinity* | *0.25* | Affinity bonus weight |
| *objective_weights.ergonomic* | *0.1* | Ergonomic penalty weight |
| *max_local_search_iterations* | *100* | Maximum swap attempts in the refinement stage |
| *inventory_simulation.coverage_days* | *14* | Simulated starting-stock coverage window |
| *inventory_simulation.train_fraction* | *0.8* | Chronological training share |
| *inventory_simulation.max_test_orders* | *0* | Zero means no explicit cap on holdout orders |

Some configuration fields are not wired into every relevant call path: the EDA script uses the affinity thresholds, but the main pipeline does not pass those settings to its affinity calculation; *objective_weights.waste* is currently unused; and *random_seed* is declared but is not consumed by the deterministic pipeline. The optimizer's heavy-SKU condition is also hard-coded separately from the configured validator threshold. These are known implementation gaps, not guarantees that every JSON field controls runtime behavior.

Warehouse dimensions, capacities, aisle spacing, and coordinates are synthetic assumptions. Replace them with surveyed site data before any real-world use.

## Repository map

    SnakeCharmers/
    ├── config/
    │   ├── simulation_config.json
    │   └── warehouse_config.json
    ├── src/
    │   ├── data_loader.py             # Load and normalize source tables
    │   ├── demand_analysis.py         # Demand profile, ABC classes, dimensional fit
    │   ├── ml_demand.py               # Ridge next-week forecast
    │   ├── affinity_analysis.py       # SKU co-occurrence
    │   ├── warehouse_generator.py    # Synthetic warehouse locations
    │   ├── baseline.py                # Candidate selection and baseline allocation
    │   ├── optimizer.py               # Greedy slotting and bounded swap refinement
    │   ├── feasibility.py              # Constraints and validation
    │   ├── routing.py                 # Simulated picking routes
    │   ├── inventory_simulation.py    # Chronological stock/picking holdout
    │   ├── milp_assortment.py         # Experimental MILP assortment selector
    │   └── evaluation.py              # Layout and route metrics
    ├── scripts/
    │   ├── download_olist.py
    │   ├── prepare_data.py
    │   ├── run_eda.py
    │   ├── run_pipeline.py
    │   └── validate_saved_layouts.py
    ├── tests/                          # Automated tests
    ├── data/raw/                       # Local source CSVs; do not commit
    ├── data/processed/                 # Generated intermediate/results CSVs
    ├── reports/                        # Generated reports and evidence
    ├── dashboard.py                   # Streamlit dashboard (known issue above)
    ├── HANDOVER.md                    # Handover notes and verification checklist
    └── requirements.txt

## Outputs

The pipeline writes normalized tables, demand profiles/forecasts, warehouse locations, baseline and optimized allocations, routes, validation tables, assortment comparisons, source-order diagnosis, and inventory-holdout artifacts under *data/processed/*. Reports are written under *reports/*.

The exact set of files and their values can change as the pipeline evolves. Use the artifacts produced by the current run rather than assuming that every file in the repository is fresh.

## Roadmap

- [ ] Fix and test the current pipeline refinement-block issue and dashboard data-loading issues.
- [ ] Add chronological rolling-origin forecast evaluation and compare Ridge with simple naïve baselines using suitable metrics.
- [ ] Benchmark alternative forecasting models only on identical time-based splits.
- [ ] Wire, remove, or document configuration fields that currently have no effect.
- [ ] Unify the heavy-SKU threshold between optimizer and validator.
- [ ] Strengthen route realism with a validated walkable path graph and measured facility data.
- [ ] Replace simulated inventory and missing hazard/handling fields with validated operational inputs before considering real-world use.
- [ ] Keep all safety unknowns visible and require review by a qualified warehouse-safety owner before operational use.

## Continuous integration

GitHub Actions in *.github/workflows/tests.yml* runs the pytest suite on pushes, pull requests, and manual dispatch using Ubuntu and Python 3.15. A green test run is useful evidence, but it does not by itself prove that the full data pipeline or interactive dashboard works end to end.

## Contributing and handover

1. Work on a feature branch and keep changes focused.
2. Run the test suite and the affected pipeline stages before opening a PR.
3. Do not commit raw data, local operational metadata, Kaggle credentials, or stale generated results without an explicit project decision.
4. When reporting a metric, include the run's source artifact and state the sample and assumptions behind it.

See [HANDOVER.md](HANDOVER.md) for the existing checklist and handover context. Verify its recorded run numbers against fresh outputs before reusing them.

<div align="center">

<sub>Built as a simulation research prototype. Do not use generated assignments operationally without validated facility data and qualified safety review.</sub>

</div>
