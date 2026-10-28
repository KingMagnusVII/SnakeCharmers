"""Small local API for the React/Vite dashboard.

Loads the generated pipeline CSVs once and keeps parsed/indexed data in memory.
This avoids reopening and reparsing the processed files on every dashboard
request.

Start from the repository root with:
    .venv\Scripts\python.exe scripts\api_server.py
"""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
HOST = "127.0.0.1"
PORT = 8000


@lru_cache(maxsize=None)
def read_csv(name: str) -> tuple[dict, ...]:
    """Read a processed CSV once per server lifetime."""
    path = PROCESSED / name
    if not path.exists():
        return ()
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return tuple(csv.DictReader(fh))


def number(value):
    try:
        n = float(value)
        return int(n) if n.is_integer() else n
    except (TypeError, ValueError):
        return value


def typed(rows) -> list[dict]:
    return [{k: number(v) for k, v in row.items()} for row in rows]


@lru_cache(maxsize=1)
def evaluation() -> dict:
    result: dict[str, dict] = {}
    for row in read_csv("evaluation_comparison.csv"):
        result[row["Metric"]] = {
            "baseline": number(row["Baseline"]),
            "optimized": number(row["Optimized"]),
            "change": number(row["Change"]),
        }
    return result


@lru_cache(maxsize=1)
def location_index() -> dict[str, dict]:
    return {r["Location_ID"]: r for r in read_csv("warehouse_locations.csv")}


@lru_cache(maxsize=1)
def allocation_index() -> dict[str, dict]:
    return {r["Location_ID"]: r for r in read_csv("optimized_allocation.csv")}


@lru_cache(maxsize=1)
def inventory() -> list[dict]:
    locations = location_index()
    rows = []
    for row in read_csv("optimized_allocation.csv"):
        loc = locations.get(row["Location_ID"], {})
        rows.append({
            "SKU_ID": row.get("SKU_ID", ""),
            "Description": row.get("SKU_ID", ""),
            "Demand_Class": row.get("Demand_Class", ""),
            "Zone": loc.get("Zone", ""),
            "Location_ID": row.get("Location_ID", ""),
            "Units": None,  # Olist has no current stock snapshot; do not invent on-hand counts.
            "Capacity": number(loc.get("Volumetric_Capacity_cm3", 0)),
            "Status": "STOCK UNKNOWN",  # Allocation is not current stock availability.
            "Unit_Value": 0,
        })
    return rows


@lru_cache(maxsize=1)
def warehouse_nodes() -> list[dict]:
    allocation = allocation_index()
    rows = []
    for loc in read_csv("warehouse_locations.csv"):
        alloc = allocation.get(loc["Location_ID"])
        rows.append({
            "Location_ID": loc.get("Location_ID", ""),
            "SKU_ID": alloc.get("SKU_ID", "—") if alloc else "—",
            "Allocation_Status": "ALLOCATED" if alloc else "VACANT",
            "X_m": number(loc.get("X_m", 0)),
            "Y_m": number(loc.get("Y_m", 0)),
            "Z_m": number(loc.get("Z_m", 0)),
            "Zone": loc.get("Zone", ""),
            "Demand_Class": alloc.get("Demand_Class", "") if alloc else "—",
            "Capacity": number(loc.get("Volumetric_Capacity_cm3", 0)),
        })
    return rows


@lru_cache(maxsize=2)
def routes(optimized: bool = True) -> list[dict]:
    name = "optimized_routes.csv" if optimized else "baseline_routes.csv"
    return typed(read_csv(name))


@lru_cache(maxsize=1)
def processed_files() -> list[str]:
    return sorted(p.name for p in PROCESSED.glob("*.csv"))


def json_response(handler: BaseHTTPRequestHandler, payload, status: int = 200):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "public, max-age=5")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                return json_response(self, {"status": "ok", "source": "Magnus pipeline"})
            if path == "/api/overview":
                return json_response(self, {"evaluation": evaluation()})
            if path == "/api/inventory":
                return json_response(self, inventory())
            if path == "/api/warehouse/nodes":
                return json_response(self, warehouse_nodes())
            if path == "/api/routes":
                optimized = parse_qs(urlparse(self.path).query).get("layout", ["optimized"])[0] != "baseline"
                return json_response(self, routes(optimized))
            if path == "/api/validation":
                baseline = [dict(row, Layout="BASELINE") for row in typed(read_csv("baseline_violations.csv"))]
                optimized = [dict(row, Layout="OPTIMIZED") for row in typed(read_csv("optimized_violations.csv"))]
                rows = baseline + optimized
                return json_response(self, {
                    "evaluation": evaluation(),
                    "baseline_violations": sum(row.get("Status") == "VIOLATION" for row in baseline),
                    "optimized_violations": sum(row.get("Status") == "VIOLATION" for row in optimized),
                    "baseline_unverified": sum(row.get("Status") == "UNVERIFIED" for row in baseline),
                    "optimized_unverified": sum(row.get("Status") == "UNVERIFIED" for row in optimized),
                    "rows": rows,
                    "available": bool(baseline or optimized),
                })
            if path == "/api/downloads":
                return json_response(self, {"files": processed_files()})
            return json_response(self, {"error": "Not found"}, 404)
        except Exception as exc:
            return json_response(self, {"error": str(exc)}, 500)

    def log_message(self, fmt, *args):
        print(f"[api] {self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    print(f"SnakeCharmers API: http://{HOST}:{PORT}")
    print(f"Pipeline data: {PROCESSED}")
    print("Processed CSVs are parsed once and cached in memory.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
