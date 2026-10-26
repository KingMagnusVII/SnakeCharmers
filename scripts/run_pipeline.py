"""Run the complete reproducible prototype pipeline."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.data_loader import load_olist_raw, normalize_olist
from src.warehouse_generator import generate_warehouse
from src.demand_analysis import analyze_demand
from src.affinity_analysis import compute_affinity
from src.baseline import allocate_baseline
from src.optimizer import optimize_layout
from src.feasibility import validate_layout
from src.routing import route_orders
from src.evaluation import evaluate, compare

def main():
    start=time.perf_counter(); out=ROOT/'data'/'processed'; reports=ROOT/'reports'; out.mkdir(exist_ok=True); reports.mkdir(exist_ok=True)
    config=json.loads((ROOT/'config'/'simulation_config.json').read_text()); tables=load_olist_raw(ROOT/'data'/'raw'); orders, skus=normalize_olist(tables); locations=generate_warehouse()
    orders.to_csv(out/'orders.csv',index=False); skus.to_csv(out/'sku_master.csv',index=False); locations.to_csv(out/'warehouse_locations.csv',index=False)
    profile, quality=analyze_demand(orders,skus,config); profile.to_csv(out/'demand_profile.csv',index=False)
    scoped=orders[orders.Order_Status.isin(config['demand_statuses'])]; active=set(profile[profile.Physical_Metadata_Usable].sort_values(['Recorded_Order_Lines','SKU_ID'],ascending=[False,True]).head(config['max_active_skus']).SKU_ID)
    affinity=compute_affinity(scoped,active); affinity.to_csv(out/'affinity_pairs.csv',index=False)
    baseline, excluded=allocate_baseline(profile,locations,config); optimized,opt_info=optimize_layout(profile,locations,baseline,affinity,config)
    baseline.to_csv(out/'baseline_allocation.csv',index=False); optimized.to_csv(out/'optimized_allocation.csv',index=False); excluded.to_csv(out/'unallocated_skus.csv',index=False)
    bv=validate_layout(baseline,skus,locations,config['allow_rotations']); ov=validate_layout(optimized,skus,locations,config['allow_rotations']); bv.to_csv(out/'baseline_violations.csv',index=False); ov.to_csv(out/'optimized_violations.csv',index=False)
    br=route_orders(scoped,baseline,locations); oroutes=route_orders(scoped,optimized,locations); br.to_csv(out/'baseline_routes.csv',index=False); oroutes.to_csv(out/'optimized_routes.csv',index=False)
    bm=evaluate(br,baseline,profile,locations,config); om=evaluate(oroutes,optimized,profile,locations,config); comparison=compare(bm,om); comparison.to_csv(out/'evaluation_comparison.csv',index=False)
    (reports/'data_foundation_audit.md').write_text('# Data foundation audit\n\nVerified raw tables, normalized schemas, 240 generated locations, and deterministic inputs.\n\n```json\n'+json.dumps(quality,indent=2,default=str)+'\n```\n',encoding='utf-8')
    (reports/'eda_report.md').write_text('# EDA report\n\nDemand scope: delivered orders. Quantity is a recorded order-line proxy, not actual units.\n\n'+json.dumps(quality,indent=2,default=str)+'\n',encoding='utf-8')
    (reports/'optimization_report.md').write_text('# Optimization report\n\nHeuristic feasible reassignment; no global optimality claim.\n\n'+json.dumps(opt_info,indent=2)+'\n',encoding='utf-8')
    (reports/'final_validation_report.md').write_text('# Final validation report\n\n```text\n'+comparison.to_string(index=False)+'\n```\n\nRuntime seconds: '+str(round(time.perf_counter()-start,2))+'\n',encoding='utf-8')
    print(json.dumps({'baseline':bm,'optimized':om,'baseline_violations':len(bv),'optimized_violations':len(ov),'runtime_seconds':round(time.perf_counter()-start,2)},indent=2))
if __name__=='__main__': main()
