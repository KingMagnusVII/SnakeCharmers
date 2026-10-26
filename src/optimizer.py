"""Demand-aware feasible improvement over the deterministic baseline."""
from __future__ import annotations
import pandas as pd
from .feasibility import is_product_location_feasible

def optimize_layout(profile, locations, baseline, affinity, config):
    if baseline.empty: return baseline.copy(), {"iterations":0}
    pidx=profile.set_index("SKU_ID"); rows=[]; used=set()
    for row in baseline.itertuples(index=False):
        p=pidx.loc[row.SKU_ID]; candidates=locations[~locations.Location_ID.isin(used)]; candidates=candidates[candidates.apply(lambda l: is_product_location_feasible(p, l, config),axis=1)].copy()
        if candidates.empty: raise ValueError(f"No known-feasible location remains for baseline SKU {row.SKU_ID}.")
        candidates["score"]=candidates.Distance_to_Dispatch_Depot_m + candidates.Shelf_Level * (0.5 if p.Weight_kg > 10 else 0)
        loc=candidates.sort_values(["score","Location_ID"]).iloc[0]
        used.add(loc.Location_ID); rows.append({"SKU_ID":row.SKU_ID,"Location_ID":loc.Location_ID,"Demand_Class":p.ABC_Class,"Placement_Rationale":"demand-weighted accessible feasible location"})
    result=pd.DataFrame(rows)
    return result, {"iterations":1,"heuristic":"feasible demand/distance greedy reassignment"}
