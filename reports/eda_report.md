# Exploratory data analysis

## Scope and provenance

This EDA reads local Olist raw tables and normalized `data/processed/orders.csv`, `sku_master.csv`, and `warehouse_locations.csv`. Demand and affinity include only `Order_Status` values configured as ['delivered']; timestamp quality is reported but timestamps are not an additional exclusion. That yields 110,197 recorded lines from 96,478 orders. Other statuses are excluded. Olist records item lines, not verified shipped-unit quantities; `Recorded_Order_Lines` is retained separately from the primary proxy, distinct orders containing a SKU.

## Quality and reconciliation

    Raw source audit is in `eda_summary.json`: 0 item lines lack an order reference, 0 lack a product reference, and the normalized-line reconciliation delta is 0. The normalized order data has 0 missing/unparseable timestamps. The demand universe has 32,216 observed-demand SKUs, 735 zero-demand product-master SKUs, and 0 observed SKUs absent from the product master. Product placement cannot be assessed for 2 products with missing/invalid dimensions and 6 with missing/invalid weight.

## Demand and ABC/Pareto

The denominator is 100,196 SKU-order incidences (the sum of per-SKU distinct-order counts), not distinct orders. Rows are ranked by distinct-order count then SKU ID. ABC uses cumulative share after each SKU: A through 80%, B through 95%, C thereafter; zero-demand rows are explicitly `ZERO` and do not affect that denominator. Counts: {'A': 12638, 'B': 14568, 'C': 5010, 'ZERO': 735}. Distinct-order frequency is a pick-frequency proxy, not inventory or unit sales.

## Affinity

Baskets deduplicate repeated SKUs within an order. Retained observed pairs require count ≥ 2 and support ≥ 0.0; 203 pairs remain. Support, both confidence directions, and lift use the same 96,478-order scope. Affinity is historical co-occurrence, not causation or proof that adjacency improves future picks.

## Dimensional fit

Warehouse locations use [{'Bin_Width_cm': 40.0, 'Bin_Height_cm': 30.0, 'Bin_Depth_cm': 40.0}]; units are centimetres, matching Olist product dimensions. The synthetic location universe has 240 locations. Of 32,949 validly measured products, 8,533 fit no location under configured rotations=True; 0 fit 1–5 locations (a descriptive, not safety, threshold). All current locations share effective bin dimensions, limiting differentiated slotting. No actual warehouse inventory/occupancy is inferred.

## Artifacts and limitations

Generated: `data/processed/demand_profile.csv`, `affinity_pairs.csv`, `dimensional_fit.csv`; charts `demand_pareto.png`, `affinity_pairs.png`, and `product_volume_distribution.png`; audit `eda_summary.json`. Warehouse geometry is synthetic, and Olist lacks inventory, hazard, handling, and verified quantities. This entry point does not run baseline allocation, optimization, routes, or evaluation.
