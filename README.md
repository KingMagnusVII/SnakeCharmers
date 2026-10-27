# SnakeCharmers — Smart Warehouse Slotting & Optimization

A reproducible research prototype that uses historical Olist e-commerce order data to profile SKU demand, forecast next-week demand, allocate a configurable active assortment to a **synthetic** warehouse, optimize slotting with a constraint-aware greedy heuristic, simulate picking routes, and compare the baseline and optimized layouts.

> **Important:** this is a simulation, not a deployment-ready warehouse safety system. The source dataset is historical (2016–2018), has no current inventory snapshot, and does not provide dependable hazard/handling classifications. Warehouse geometry and route distances are synthetic. Unknown safety data must remain unverified.

## Quick start (Windows PowerShell)

Run commands from the repository root:

```powershell
git checkout Magnus
git pull origin Magnus
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m scripts.run_pipeline
.venv\Scripts\python.exe scripts\validate_saved_layouts.py
.venv\Scripts\python.exe -m streamlit run dashboard.py
```

If setting up from scratch:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The Streamlit command prints a local URL. Open it in a browser and stop the server with Ctrl+C.

## Input data: Kaggle / Olist

Source: [Olist Brazilian E-Commerce Public Dataset on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). The original dataset covers Brazilian marketplace orders from 2016–2018. Raw data is not committed to this repository.

Download and prepare the data from the repository root:

```powershell
.venv\Scripts\python.exe -m scripts.download_olist
.venv\Scripts\python.exe -m scripts.prepare_data
```

The download requires Kaggle account access, acceptance of dataset terms, and Kaggle API credentials. The project currently loads **only three of the nine original Olist CSVs**. The other Olist tables are not currently model inputs.

### Exact raw CSV columns used by this code

| Olist CSV | Columns required/read by this project | How the project uses them |
|---|---|---|
| `olist_orders_dataset.csv` | `order_id`, `order_purchase_timestamp`, `order_status` | Join key, demand timestamp, and filter for demand status. Other order columns are not currently used. |
| `olist_order_items_dataset.csv` | `order_id`, `order_item_id`, `product_id`, `price`, `freight_value` | Order/SKU relationship; item ID; price and freight retained in normalized data. Each recorded order-item row is treated as one demand-line observation. |
| `olist_products_dataset.csv` | `product_id`, `product_category_name`, `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm` | SKU identifier, category, dimensions, and weight. Weight is converted from grams to kilograms; length is mapped to project depth. |

The following original files are **not currently read by the pipeline**: `olist_customers_dataset.csv`, `olist_order_payments_dataset.csv`, `olist_order_reviews_dataset.csv`, `olist_sellers_dataset.csv`, `olist_geolocation_dataset.csv`, and `product_category_name_translation.csv`. Fields in those files must not be described as current model features. They may be considered in a future version only if they support a clearly defined warehouse objective and can be joined/validated correctly.

### Source-to-project transformations and limitations

- Raw `order_id` becomes `Order_ID`; `product_id` becomes `SKU_ID`; `order_purchase_timestamp` becomes `Timestamp`; `order_status` becomes `Order_Status`.
- Olist's order-item table has no reliable explicit item quantity field. The project sets normalized `Quantity = 1.0` for each recorded item line. Forecast demand therefore means **recorded order-item lines**, not verified physical units sold or units currently in stock.
- The demand scope is controlled by `demand_statuses`, currently `["delivered"]`.
- Product dimensions are used for physical fit checks. `Volume_cm3` is calculated as width × height × depth; rotation is checked against bin dimensions when enabled.
- `Hazard_Class` and `Handling_Type` are set to `UNSPECIFIED`; `Inventory_Units` is missing because the source data does not contain a current inventory snapshot.
- The configured `representative_inventory_units = 1` is a **simulation fallback**, not an observed quantity. Validation still marks the corresponding inventory checks as `UNVERIFIED`.
- Do not infer hazard class, safe handling, or storage compatibility from a product category name.

## Resolving inventory and safety-data gaps

The Olist dataset is historical sales data, not a warehouse management system. It cannot tell us current on-hand stock, verified hazard classifications, handling requirements, or whether a real rack/floor is rated for the modeled load. The pipeline therefore leaves those attributes unknown instead of inventing them. The default one-unit representative-stock value is for simulation only.

### Add reviewed operational SKU data

1. Copy templates/sku_operational_metadata_template.csv to data/input/sku_operational_metadata.csv. The data/input/ directory is intentionally git-ignored because it may contain sensitive inventory and safety information.
2. Add one row per SKU you can verify. SKU_ID must exactly match the Olist product ID in sku_master.csv. Leave fields blank when you do not have trustworthy data; do not guess.
3. For a supplied Inventory_Units, enter the current whole-number on-hand quantity (zero is valid), the snapshot timestamp in Inventory_Snapshot_At, and the system/report used in Inventory_Data_Source.
4. For supplied Hazard_Class or Handling_Type, enter the classification approved for that product and complete Safety_Verified_By, Safety_Verified_At, and Safety_Data_Source. Use values such as NONE or NORMAL only when the responsible source explicitly confirms them. UNKNOWN and UNSPECIFIED are not accepted as reviewed values.
5. Re-run data preparation and the pipeline so the overlay is merged into the generated SKU master:

```powershell
.venv\Scripts\python.exe -m scripts.prepare_data
.venv\Scripts\python.exe -m scripts.run_pipeline
.venv\Scripts\python.exe scripts\validate_saved_layouts.py
```

The data-foundation audit records whether the overlay was found and how many inventory and safety records were applied. Invalid quantities, duplicate IDs, unknown SKUs, missing provenance, and invalid dates stop preparation with an actionable error.

### Require complete metadata before operational review

```powershell
.venv\Scripts\python.exe scripts\validate_saved_layouts.py --strict-operational-data
```

The strict check exits with code 2 when any allocated SKU is missing a non-negative inventory count, non-placeholder hazard/handling classifications, or the required provenance fields. A successful check means the SKU metadata is complete enough for the next review step; **it is not a safety certification and does not prove the warehouse geometry, rack ratings, compatibility policy, fire controls, aisle clearances, or ergonomics are safe**. Those must be verified against the actual facility and reviewed by the responsible warehouse/safety owner.

The ordinary validator remains available for simulation runs and continues to report missing data as UNVERIFIED. Do not change representative_inventory_units to make missing stock appear known.

### Remaining real-world requirements

- **Inventory:** connect a WMS/ERP snapshot with a timestamp, unit of measure, SKU identity, and a documented reconciliation process. Historical demand is not inventory. Confirm whether the modeled quantity means eaches, cases, pallets, or another handling unit before using capacity calculations.
- **Product safety:** use an approved product master/SDS or internal safety register for hazard class, handling method, storage restrictions, and any incompatibilities. A product category is not evidence of chemical compatibility.
- **Facility constraints:** replace synthetic coordinates, bin sizes, and load limits with measured locations and verified rack/shelf/floor ratings. Add real aisle/exit clearances, access restrictions, and site-approved storage rules.
- **Operational sign-off:** have the warehouse owner validate the inputs and rules before any generated allocation is used to store or move physical goods.

These controls align with general warehouse-storage principles such as respecting rated loads, segregating incompatible materials, maintaining clear aisles, and preventing unstable storage; applicability and detailed requirements depend on the actual jurisdiction and facility. See [OSHA warehouse hazards and solutions](https://www.osha.gov/warehousing/hazards-solutions) and [OSHA general storage requirements](https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926.250).

## Current AI / optimization pipeline

There are two distinct components: (1) a supervised **Ridge regression demand forecast**, and (2) a rule/heuristic-based **slotting optimizer**. The second component is not itself a trained AI model.

### 1. Demand forecast — current model and every feature

Implementation: `src/ml_demand.py`.

| Setting / feature | Current value or definition | Role |
|---|---|---|
| Estimator | scikit-learn `Ridge` regression | Predicts next-week SKU demand. |
| Ridge regularization `alpha` | `1.0` | Controls coefficient regularization. |
| Prediction target | Weekly count of recorded order-item lines per SKU | Target is transformed with `log1p` during training. |
| Forecast horizon | Next week | One-step-ahead forecast for each SKU. |
| `Lag_1` | Previous week's recorded line count | Recent demand signal. |
| `Lag_4` | Recorded line count four weeks earlier | Seasonal/recent-history signal; it is not a full seasonal model. |
| `Rolling_4` | Mean of up to the previous four weekly counts, shifted so the current target week is excluded | Recent demand level. |
| `Historical_Mean` | Expanding mean of previous weekly counts, shifted to exclude the current target week | Longer-term SKU demand level. |
| `Week_Index` | Number of weeks from the first observed week, as a numeric trend | Captures a simple time trend. |
| `Category` | Olist `product_category_name`, mapped to normalized `Category` | Product context, one-hot encoded. |

**Preprocessing and training behavior**

- Demand observations are filtered to configured `demand_statuses` (currently `delivered`).
- Timestamps are converted to dates and bucketed into weekly periods. Missing SKU/week combinations are filled with zero demand.
- Training rows require non-missing `Lag_1`, `Lag_4`, `Rolling_4`, and `Historical_Mean`. Training is skipped if fewer than 20 rows remain.
- Numeric features use median imputation followed by `StandardScaler`.
- `Category` uses most-frequent imputation and `OneHotEncoder(handle_unknown="ignore")`.
- The Ridge model is trained on `log1p(weekly_demand)`; predictions are transformed back with `expm1` and clipped to be non-negative.
- If there are no valid timestamps or too few rows, the model reports `trained = false` and the initialized predictions remain zero. Check the generated ML report for actual run status.
- This code currently fits on the available historical series and produces the next-week forecast. It does **not yet report a proper held-out, rolling-origin forecast score**; that is required before claiming the model is accurate.

### 2. How the forecast influences slotting

Implementation: `src/optimizer.py`.

- SKUs are considered in descending `Predicted_Next_Week_Demand` order (SKU ID breaks ties). High forecast demand therefore gets first access to feasible locations.
- Hard feasibility checks include dimensional fit, location volume/weight limits, configured shelf/rack loads, and configured incompatibility rules. Unknown hazard/handling information is reported as unverified, not as proof of safety.
- Candidate-location score currently minimizes:

  `distance_weight × depot_distance + ergonomic_weight × heavy_shelf_penalty − affinity_weight × affinity_proximity_bonus`

- The current objective weights are `distance = 1.0`, `affinity = 0.25`, and `ergonomic = 0.1`.
- The ergonomic penalty is currently based on shelf level and whether product weight exceeds the hard-coded 10 kg condition inside the optimizer. The validator separately uses the configured ergonomic threshold; these should be unified in a future cleanup.
- Affinity is computed from SKUs appearing together in the same order. Pair strength is `log1p(Pair_Count) × log1p(Lift)`; affinity proximity rewards placing related SKUs near each other using Manhattan distance normalized by the maximum depot-distance value.
- The baseline allocator is deterministic and historically demand-ranked; the optimized allocator uses the ML forecast priority. Both are evaluated on the same baseline-selected active assortment.
- This is a one-pass greedy heuristic. It does not prove global optimality or guarantee that a better layout cannot exist.

### 3. Configuration parameters

The main run configuration is `config/simulation_config.json`.

| Parameter | Current value | What it controls / status |
|---|---|---|
| `demand_statuses` | `["delivered"]` | Which order lines enter demand analysis, forecasting, affinity, and route simulation. |
| `max_active_skus` | `200` | Maximum assortment size selected for allocation/evaluation. |
| `representative_inventory_units` | `1` | Fallback used when observed inventory is absent; simulation assumption only. |
| `allow_rotations` | `true` | Allows dimension permutations when checking physical fit. |
| `ergonomics.heavy_sku_weight_kg` | `10.0` | Configured weight threshold used by feasibility validation. |
| `ergonomics.max_shelf_level_for_heavy_skus` | `2` | Configured maximum shelf level for heavy SKUs in validation. |
| `incompatibility_rules.category_hazard_pairs` | `[]` | Explicit category/hazard incompatibility rules; none currently supplied. |
| `incompatibility_rules.hazard_handling_pairs` | `[]` | Explicit hazard/handling incompatibility rules; none currently supplied. |
| `abc_thresholds` | A: `0.80`, B: `0.95` | Cumulative demand-share thresholds for ABC classification. |
| `affinity_min_pair_count` | `2` | Declared setting, but the current pipeline does not pass it into `compute_affinity`; the function's default `min_pair_count=1` is therefore used. |
| `affinity_min_support` | `0.0` | Declared setting, but the current pipeline does not pass it into `compute_affinity`; the function's default `min_support=0.0` is therefore used. |
| `walking_speed_m_per_min` | `75.0` | Assumed speed for estimated picking time, not measured speed. |
| `pick_handling_seconds` | `12.0` | Assumed handling time per simulated order. |
| `objective_weights.distance` | `1.0` | Weight on depot distance in greedy candidate score. |
| `objective_weights.affinity` | `0.25` | Weight on affinity proximity bonus. |
| `objective_weights.ergonomic` | `0.1` | Weight on the optimizer's shelf-level penalty. |
| `objective_weights.waste` | `0.00001` | Present in config but not currently used by the greedy optimizer. |
| `random_seed` | `42` | Present in config; current pipeline stages described here are deterministic and do not currently consume this setting. |
| `max_local_search_iterations` | `100` | Present in config but not currently used; the current optimizer performs one greedy pass. |

The current routing simulation also has `max_orders=500` as a default argument in `src/routing.py`. The current Ridge implementation uses fixed settings in code (`alpha=1.0`, median imputation, standard scaling, most-frequent category imputation, one-hot encoding, and a minimum of 20 training rows); these are not currently exposed as JSON configuration parameters.

Warehouse geometry is configured separately in `config/warehouse_config.json`: 6 aisles; two rack sides per aisle; 5 bays per rack; 4 shelf levels; aisle spacing 3.0 m; bay spacing 1.2 m; first aisle X = 3.0 m; first bay Y = 2.0 m; default bin dimensions 40 × 30 × 40 cm; levels 1 and 2 use 100 × 60 × 60 cm bins; level weight capacities 40/35/30/20 kg; shelf limit 200 kg; rack limit 700 kg; and four dedicated oversized slots with their own configured dimensions, capacities, and coordinates. These are synthetic assumptions and must be replaced with measured site data for a real warehouse.

## Future AI upgrade plan

A more powerful model should be introduced only after a reproducible evaluation proves it improves on Ridge. Recommended staged plan:

1. **Establish a trustworthy baseline:** add chronological rolling-origin/backtesting splits so every validation forecast uses only data available before that forecast week. Report MAE, RMSE, and WAPE (with the WAPE zero-denominator case handled explicitly), overall and by demand segment/category. Compare against simple naïve baselines such as last-week demand and recent moving average.
2. **Benchmark stronger tabular models:** test gradient-boosted trees such as HistGradientBoosting or an available LightGBM/CatBoost option against Ridge using identical time splits and features. Evaluate global models across SKUs; do not assume a deep neural network is automatically better for this dataset.
3. **Add features only when justified:** test calendar/seasonality features, richer lag windows, promotion/price signals if reliable, and product attributes. Avoid data leakage: no feature may use future order information. Olist's short historical period and old data should be explicitly considered.
4. **Improve the slotting optimizer separately:** benchmark local search, simulated annealing, or a formal constraint solver such as OR-Tools against the current greedy result. Keep hard feasibility constraints separate from soft objectives and report runtime/solution quality.
5. **Use a fair acceptance gate:** preserve the current Ridge + greedy version as a baseline. Adopt a replacement only when time-based test performance and end-to-end slotting metrics improve consistently, runtime is acceptable, tests pass, and safety/inventory data quality is not hidden by the model.

Potential future model inputs should be documented by exact source field, transformation, missing-value treatment, and whether each feature is available at prediction time. Do not include customer/review/payment/geolocation fields just because they exist in Kaggle; first show that they improve a defined warehouse demand or routing objective without leakage.

## Pipeline stages

1. Load and normalize the three required Olist tables.
2. Build demand profile and ABC demand classes.
3. Forecast next-week demand with Ridge.
4. Compute SKU co-occurrence affinity.
5. Generate synthetic warehouse locations.
6. Allocate the active assortment using a deterministic feasible baseline.
7. Reassign feasible slots using forecast priority, distance, affinity, and ergonomic heuristics.
8. Simulate nearest-next-SKU picking routes using Manhattan distance.
9. Compare route distance/time, coverage, utilization, and validation completeness.
10. Save reports and CSV outputs for the Streamlit dashboard.

## Outputs

Generated CSVs are written under `data/processed/` (typically ignored by Git); reports are written under `reports/`. Important reports include:

- `data_foundation_audit.md`
- `eda_report.md`
- `ml_demand_report.md`
- `optimization_report.md`
- `unallocated_sku_diagnosis.md`
- `final_validation_report.md`

## Interpreting results safely

- **Active assortment coverage** is the percentage of selected SKUs allocated; it is not coverage of the full product catalog.
- **Catalog-wide allocation coverage** uses the full SKU profile as its denominator and can be low when only a limited assortment is modeled.
- **Whole-warehouse utilization** and **allocated-bin utilization** have different capacity denominators.
- **Confirmed violations** and **UNVERIFIED checks** are separate. Unknown inventory, hazard, or handling attributes are not evidence that a layout is safe.
- **Demand forecast** estimates next-week recorded order-line counts from historical Olist records; it is not a real-time inventory or replenishment system.
- **Route distance/time** are estimates from a simplified synthetic geometry, not measured warehouse performance.
- The optimizer is a greedy heuristic, not a globally optimal solver.

See [HANDOVER.md](HANDOVER.md) for setup, verification checklist, known limitations, and transfer notes.
