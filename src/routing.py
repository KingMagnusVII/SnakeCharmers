"""Walkable aisle approximation and deterministic multi-stop routes."""
from __future__ import annotations
import math
import pandas as pd

def route_orders(orders, layout, locations, max_orders=500):
    loc = layout.merge(locations[["Location_ID","X_m","Y_m"]], on="Location_ID", how="left").set_index("SKU_ID")
    records=[]
    for order_id, group in orders.groupby("Order_ID", sort=True):
        if len(records) >= max_orders: break
        skus=list(dict.fromkeys(group.SKU_ID)); present=[s for s in skus if s in loc.index]
        if not present: continue
        current=(0.0,0.0); remaining=present[:]; path=[]; distance=0.0
        while remaining:
            sku=min(remaining, key=lambda s: abs(loc.loc[s].X_m-current[0])+abs(loc.loc[s].Y_m-current[1])); point=(loc.loc[sku].X_m,loc.loc[sku].Y_m); distance += abs(point[0]-current[0])+abs(point[1]-current[1]); path.append(sku); current=point; remaining.remove(sku)
        distance += abs(current[0])+abs(current[1])
        records.append({"Order_ID":order_id,"Visited_SKUs":"|".join(path),"Distance_m":distance,"Complete":len(present)==len(skus)})
    return pd.DataFrame(records)
