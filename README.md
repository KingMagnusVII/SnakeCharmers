# SnakeCharmers — Smart Warehouse Slotting & Optimization

EPOCH Hackathon project: a constraint-aware warehouse slotting engine that assigns SKUs to storage locations and evaluates picking efficiency against a feasible baseline.

## Step 1 — Data foundation

The repository now includes a reproducible prototype pipeline from Olist normalization through demand profiling, feasible baseline allocation, heuristic optimization, route simulation, evaluation, and a Streamlit dashboard.

### Data sources
- Orders and product metadata: [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
- Warehouse topology: synthetic, generated from config/warehouse_config.json because Olist does not include warehouse racks, bins, aisle coordinates, or storage load ratings.
- Hazard/handling attributes and current inventory: not reliably provided by Olist. Such values are left unspecified rather than represented as real data.

Raw and processed data are excluded from Git.

## Setup

Use Python 3.11+ (required by the pandas 3.x dependency range).

    python -m venv .venv
    # macOS/Linux
    source .venv/bin/activate
    # Windows PowerShell: .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt

## 1. Download Olist

1. Sign in to Kaggle and accept the dataset terms.
2. Configure Kaggle API credentials: https://github.com/Kaggle/kaggle-api#api-credentials
3. Run from the repository root:

    python -m scripts.download_olist

This downloads and extracts CSV files to data/raw/.

## 2. Prepare normalized inputs

    python -m scripts.prepare_data

Outputs:
- data/processed/orders.csv — order-item demand lines, timestamps, status, price and freight.
- data/processed/sku_master.csv — product dimensions, weight, category, and explicitly unspecified handling/hazard attributes.
- data/processed/warehouse_locations.csv — generated bins/racks/shelves with coordinates and capacity metadata.

**Important Olist limitation:** its order-item table does not provide an explicit quantity field. Quantity=1 is used as a transparent per-order-item proxy, not as a claim that Olist records a real line quantity. We will review this during EDA. Olist also has no current inventory snapshot, so Inventory_Units remains blank until a documented synthetic-stock assumption is chosen.

## Synthetic topology defaults

6 aisles × 2 rack sides × 5 bays × 4 shelf levels = 240 locations. Geometry, bin size, dispatch point, and capacity ratings can be changed in config/warehouse_config.json. These are simulation assumptions, not real engineering/safety ratings. Distance_to_Dispatch_Depot_m is initially a Manhattan-distance approximation; route simulation will later use walkable aisles.

## Architecture

    smart-warehouse/
    ├── config/warehouse_config.json
    ├── data/raw/                 # downloads, ignored by Git
    ├── data/processed/           # generated CSVs, ignored by Git
    ├── src/
    │   ├── data_loader.py
    │   ├── warehouse_generator.py
    │   ├── demand_analysis.py   # next stage
    │   ├── affinity_analysis.py # next stage
    │   ├── feasibility.py       # next stage
    │   ├── baseline.py          # next stage
    │   ├── optimizer.py         # next stage
    │   ├── routing.py           # next stage
    │   └── evaluation.py        # next stage
    ├── scripts/download_olist.py
    ├── scripts/prepare_data.py
    ├── tests/
    ├── reports/
    └── dashboard.py              # later stage

## Assumptions to revisit
- Product length maps to Depth_cm, and product weight in grams is converted to kilograms.
- Missing physical attributes are preserved for EDA instead of silently imputed.
- Hazard_Class and Handling_Type are UNSPECIFIED; these should not be guessed from product category.
- Warehouse capacity/zone data is synthetic, and must be treated as configurable simulation inputs.
- The allocation stage must report infeasible products rather than forcing an unsafe fit.

## Run the complete pipeline

From the repository root in the project `.venv`:

    .venv\Scripts\python.exe scripts\run_pipeline.py

The runner uses existing local raw data, regenerates normalized and generated outputs deterministically, and writes allocations, routes, violations, comparisons, and reports under `data/processed/` and `reports/`.

Launch the dashboard after the pipeline has completed:

    .venv\Scripts\python.exe -m streamlit run dashboard.py

Run tests with:

    .venv\Scripts\python.exe -m pytest -q

## Method and limitations

The active assortment is configurable in `config/simulation_config.json` and defaults to up to 200 demand-ranked SKUs with usable dimensions and weight. The first prototype models one representative unit per selected SKU; this is not an Olist inventory observation. Quantity remains one recorded order-item line, hazard and handling remain unspecified, and the warehouse topology and capacity ratings are synthetic.

The baseline is deterministic and hard-constraint aware. The optimizer is a feasible greedy reassignment using demand accessibility and ergonomic preferences; it is a heuristic and has no global optimality guarantee. Route distances use a deterministic Manhattan aisle approximation until a measured walkable graph is available. Metrics are generated from actual local inputs and are scoped to the active assortment and simulated route sample.

See `reports/data_foundation_audit.md`, `reports/eda_report.md`, `reports/optimization_report.md`, and `reports/final_validation_report.md` after running the pipeline.

## Constraint-validation evidence

The independent validator treats missing Olist inventory, hazard, and handling information as **UNVERIFIED**, never as safety-compliant. Its representative-stock fallback is explicitly configured in `config/simulation_config.json`; bin, location, shelf, rack, dimension, ergonomic, and configured known-incompatibility checks use this model. The heavy-SKU placement rule is a prototype assumption (over 10 kg must be on shelf level 1 or 2), not a regulatory conclusion. No category or hazard rule is inferred from Olist; documented rules must be added to the configuration before they can be enforced.

Validate the existing saved layouts without regenerating the pipeline:

    .venv\Scripts\python.exe scripts\validate_saved_layouts.py
