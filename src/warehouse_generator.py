"""Generate a configurable synthetic warehouse grid."""
from __future__ import annotations  # Enables modern type annotations.

import json  # Reads the warehouse configuration file.
from pathlib import Path  # Handles configuration paths.

import pandas as pd  # Builds the generated location table.

# Locate the repository root and default warehouse configuration.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "warehouse_config.json"


def generate_warehouse(config_path: Path = DEFAULT_CONFIG) -> pd.DataFrame:
    """Generate bins, racks, shelves, coordinates, and capacity metadata."""

    # Read the configurable synthetic warehouse definition.
    config = json.loads(config_path.read_text(encoding="utf-8"))

    # Extract the main geometry and capacity settings.
    depot = config["dispatch_depot"]
    dims = config["bin_dimensions_cm"]
    levels = int(config["shelf_levels_per_rack"])
    bays = int(config["bays_per_rack"])
    zone_ranges = config["zone_aisle_ranges"]

    # Compute the volume of one configured bin.
    volume = float(dims["width"]) * float(dims["height"]) * float(dims["depth"])

    def zone_for(aisle: int) -> str:
        """Return the configured zone containing an aisle."""

        # Search each configured inclusive aisle range.
        for zone, bounds in zone_ranges.items():
            if int(bounds[0]) <= aisle <= int(bounds[1]):
                return zone

        # Aisles outside all configured ranges are explicitly marked.
        return "UNZONED"

    # Collect generated location dictionaries before creating the DataFrame.
    rows: list[dict] = []

    # Generate each aisle in numeric order.
    for aisle in range(1, int(config["aisles"]) + 1):
        # Calculate the X coordinate for this aisle.
        x = float(config["first_aisle_x_m"]) + (
            aisle - 1
        ) * float(config["aisle_spacing_m"])

        # Generate both rack sides configured for this aisle.
        for side in config["rack_sides_per_aisle"]:
            rack_id = f"A{aisle:02d}-{side}"

            # Generate every bay along the rack.
            for bay in range(1, bays + 1):
                # Calculate the Y coordinate for this bay.
                y = float(config["first_bay_y_m"]) + (
                    bay - 1
                ) * float(config["bay_spacing_m"])

                # Generate every shelf level in the bay.
                for level in range(1, levels + 1):
                    # Model shelf height using the configured level spacing.
                    z = 0.35 + (level - 1) * 0.75

                    # Append all metadata needed by allocation and validation.
                    rows.append(
                        {
                            "Location_ID": f"A{aisle:02d}-R{side}-B{bay:02d}-L{level:02d}",
                            "Zone": zone_for(aisle),
                            "Aisle_Number": aisle,
                            "Rack_ID": rack_id,
                            "Bay": bay,
                            "Shelf_Level": level,
                            "X_m": round(x, 3),
                            "Y_m": round(y, 3),
                            "Z_m": round(z, 3),
                            "Bin_Width_cm": float(dims["width"]),
                            "Bin_Height_cm": float(dims["height"]),
                            "Bin_Depth_cm": float(dims["depth"]),
                            "Volumetric_Capacity_cm3": round(volume, 2),
                            "Max_Weight_Capacity_kg": float(
                                config["location_weight_capacity_by_level_kg"][str(level)]
                            ),
                            "Shelf_Max_Load_kg": float(config["shelf_max_load_kg"]),
                            "Rack_Max_Load_kg": float(config["rack_max_load_kg"]),
                            # Current distance is a Manhattan-distance proxy.
                            "Distance_to_Dispatch_Depot_m": round(
                                abs(x - float(depot["x_m"]))
                                + abs(y - float(depot["y_m"])),
                                2,
                            ),
                        }
                    )

    # Convert all generated locations into a DataFrame.
    result = pd.DataFrame(rows)

    # Refuse to silently continue if generation produced duplicate identifiers.
    if result["Location_ID"].duplicated().any():
        raise ValueError("Generated duplicate Location_ID values.")

    # Return the complete synthetic warehouse topology.
    return result
