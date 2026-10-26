"""Deterministic constrained baseline allocation."""
from __future__ import annotations
import pandas as pd
from .feasibility import is_product_location_feasible

def allocate_baseline(profile: pd.DataFrame, locations: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_skus = int(config.get("max_active_skus", 200)); eligible = profile[profile.Physical_Metadata_Usable].sort_values(["Recorded_Order_Lines","SKU_ID"], ascending=[False,True]).head(max_skus).copy()
    used=set(); rows=[]; excluded=[]
    for _, p in eligible.sort_values(["Width_cm","Height_cm","Depth_cm","SKU_ID"], ascending=[False,False,False,True]).iterrows():
        choices = locations[~locations.Location_ID.isin(used)]
        match = choices[choices.apply(lambda l: is_product_location_feasible(p, l, config), axis=1)].sort_values("Location_ID")
        if match.empty: excluded.append({"SKU_ID":p.SKU_ID,"Reason":"infeasible_or_no_remaining_location"}); continue
        loc=match.iloc[0]; used.add(loc.Location_ID); rows.append({"SKU_ID":p.SKU_ID,"Location_ID":loc.Location_ID,"Demand_Class":p.ABC_Class,"Placement_Rationale":"deterministic constrained-first baseline"})
    return pd.DataFrame(rows), pd.DataFrame(excluded)
