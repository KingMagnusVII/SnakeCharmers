# SnakeCharmers — Smart Warehouse Slotting & Optimization

EPOCH Hackathon project: a constraint-aware warehouse slotting engine that assigns SKUs to storage locations and evaluates picking efficiency against a feasible baseline.

## Step 1 — Data foundation

This stage sets up reproducible dataset acquisition, schema normalization, and synthetic warehouse topology. EDA, validation, optimization, routing, and dashboard work will be added sequentially after this foundation is reviewed.

### Data sources
- Orders and product metadata: [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
- Warehouse topology: synthetic, generated from config/warehouse_config.json because Olist does not include warehouse racks, bins, aisle coordinates, or storage load ratings.
- Hazard/handling attributes and current inventory: not reliably provided by Olist. Such values are left unspecified rather than represented as real data.

Raw and processed data are excluded from Git.

## Setup

Use Python 3.10+.

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

## Next stages
1. Review and run this data foundation.
2. Conduct data-quality checks, demand ABC/Pareto profiling, co-order affinity, and volume EDA.
3. Build hard-constraint validation and a feasible baseline.
4. Build demand-/affinity-aware optimization and local search.
5. Simulate pick routes using identical orders/settings for both layouts.
6. Build the dashboard and technical documentation.
