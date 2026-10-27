"""Independent hard-constraint validation for one-SKU-per-location layouts.

The validator reports both demonstrable violations and checks that cannot be
verified from Olist-derived inputs. ``UNVERIFIED`` never means compliant.
"""
from __future__ import annotations

from itertools import permutations
from typing import Any, Mapping

import pandas as pd


RESULT_COLUMNS = ["SKU_ID", "Location_ID", "Rule", "Status", "Measured", "Limit", "Details"]


def _number(value: Any) -> float | None:
    value = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(value) else float(value)


def _result(sku: Any, location: Any, rule: str, status: str, measured: Any, limit: Any, details: str) -> dict[str, Any]:
    return {"SKU_ID": "" if pd.isna(sku) else sku, "Location_ID": "" if pd.isna(location) else location, "Rule": rule, "Status": status, "Measured": measured, "Limit": limit, "Details": details}


def _config(config: Mapping[str, Any] | bool | None, allow_rotations: bool | None) -> dict[str, Any]:
    """Support the former boolean fourth argument while accepting full config."""
    result = {"allow_rotations": config} if isinstance(config, bool) else dict(config or {})
    if allow_rotations is not None:
        result["allow_rotations"] = allow_rotations
    return result


def _dimensions(product: pd.Series) -> tuple[list[float] | None, list[dict[str, Any]]]:
    values: list[float] = []
    results: list[dict[str, Any]] = []
    for column in ("Width_cm", "Height_cm", "Depth_cm"):
        value = _number(product.get(column))
        if value is None:
            results.append(_result(product.get("SKU_ID"), "", "missing_physical_dimension", "UNVERIFIED", column, "positive numeric value", "Product dimension is unavailable."))
        elif value <= 0:
            results.append(_result(product.get("SKU_ID"), "", "invalid_physical_dimension", "VIOLATION", {column: value}, "> 0", "Product dimensions must be positive."))
        values.append(value if value is not None else float("nan"))
    return (None if results else values), results


def fits_product(product: pd.Series, location: pd.Series, allow_rotations: bool = True) -> bool:
    """Return whether positive dimensions fit the bin in an allowed orientation."""
    dims, problems = _dimensions(product)
    bin_dims = [_number(location.get(column)) for column in ("Bin_Width_cm", "Bin_Height_cm", "Bin_Depth_cm")]
    if problems or dims is None or any(value is None or value <= 0 for value in bin_dims):
        return False
    orientations = permutations(dims) if allow_rotations else (dims,)
    return any(all(product_dim <= bin_dim for product_dim, bin_dim in zip(orientation, bin_dims)) for orientation in orientations)


def _stock_units(product: pd.Series, config: Mapping[str, Any]) -> tuple[float | None, bool, str | None]:
    units = _number(product.get("Inventory_Units"))
    if units is None:
        fallback = _number(config.get("representative_inventory_units", 1))
        if fallback is None or fallback <= 0:
            return None, False, "Configured representative_inventory_units must be a positive numeric value."
        return fallback, True, "Observed inventory is unavailable; representative-stock assumption is used."
    if units < 0:
        return None, False, "Inventory units cannot be negative."
    return units, False, None


def modeled_stock_load_kg(product: pd.Series, config: Mapping[str, Any]) -> float | None:
    """Return SKU stock load using observed inventory or the simulation fallback."""
    units, _, _ = _stock_units(product, config)
    weight = _number(product.get("Weight_kg"))
    if units is None or weight is None or weight < 0:
        return None
    return units * weight


def rack_load_fits(
    product: pd.Series,
    location: pd.Series,
    current_rack_loads: Mapping[Any, float],
    config: Mapping[str, Any],
) -> bool:
    """Check whether this SKU's modeled stock fits the remaining rack capacity."""
    load = modeled_stock_load_kg(product, config)
    limit = _number(location.get("Rack_Max_Load_kg"))
    rack_id = location.get("Rack_ID")
    if load is None or limit is None:
        # Missing capacity evidence remains UNVERIFIED and is caught by validation.
        return True
    return float(current_rack_loads.get(rack_id, 0.0)) + load <= limit


def _known_incompatibility(product: pd.Series, config: Mapping[str, Any]) -> list[str]:
    rules = config.get("incompatibility_rules", {}) or {}
    category, hazard, handling = product.get("Category"), product.get("Hazard_Class"), product.get("Handling_Type")
    matches = []
    for rule in rules.get("category_hazard_pairs", []):
        if category == rule.get("category") and hazard == rule.get("hazard_class"):
            matches.append(f"category={category}, hazard_class={hazard}")
    for rule in rules.get("hazard_handling_pairs", []):
        if hazard == rule.get("hazard_class") and handling == rule.get("handling_type"):
            matches.append(f"hazard_class={hazard}, handling_type={handling}")
    return matches


def product_location_results(product: pd.Series, location: pd.Series, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Check known constraints for one proposed placement."""
    config = dict(config or {})
    sku, location_id = product.get("SKU_ID"), location.get("Location_ID")
    results: list[dict[str, Any]] = []
    dims, dimension_problems = _dimensions(product)
    for problem in dimension_problems:
        problem["Location_ID"] = location_id
        results.append(problem)
    weight = _number(product.get("Weight_kg"))
    if weight is None:
        results.append(_result(sku, location_id, "missing_weight_kg", "UNVERIFIED", "Weight_kg", "positive numeric value", "Weight-dependent checks cannot be fully verified."))
    elif weight <= 0:
        results.append(_result(sku, location_id, "invalid_weight_kg", "VIOLATION", weight, "> 0", "Product weight must be positive."))
    bin_columns = ("Bin_Width_cm", "Bin_Height_cm", "Bin_Depth_cm")
    bin_dimensions = [_number(location.get(column)) for column in bin_columns]
    if dims is not None:
        missing_bin_dimensions = [column for column, value in zip(bin_columns, bin_dimensions) if value is None]
        invalid_bin_dimensions = {column: value for column, value in zip(bin_columns, bin_dimensions) if value is not None and value <= 0}
        if missing_bin_dimensions:
            results.append(_result(sku, location_id, "missing_bin_dimension", "UNVERIFIED", missing_bin_dimensions, "positive numeric values", "Bin dimensions are incomplete; dimensional fit cannot be verified."))
        if invalid_bin_dimensions:
            results.append(_result(sku, location_id, "invalid_bin_dimension", "VIOLATION", invalid_bin_dimensions, "> 0", "Bin dimensions must be positive."))
        if not missing_bin_dimensions and not invalid_bin_dimensions and not fits_product(product, location, bool(config.get("allow_rotations", True))):
            results.append(_result(sku, location_id, "dimensional_fit", "VIOLATION", dims, bin_dimensions, "No permitted orientation fits this bin."))

    units, assumed_units, unit_note = _stock_units(product, config)
    if units is None:
        inventory_value = product.get("Inventory_Units")
        missing_inventory = _number(inventory_value) is None
        rule = "invalid_representative_inventory_units" if missing_inventory else "invalid_inventory_units"
        measured = config.get("representative_inventory_units", 1) if missing_inventory else inventory_value
        results.append(_result(sku, location_id, rule, "VIOLATION", measured, "> 0", unit_note or "Inventory units must be positive."))
    else:
        if assumed_units:
            results.append(_result(sku, location_id, "inventory_units", "UNVERIFIED", "missing", units, unit_note or ""))
        if dims is not None:
            modeled_volume = dims[0] * dims[1] * dims[2] * units
            capacity = _number(location.get("Volumetric_Capacity_cm3"))
            if capacity is None:
                results.append(_result(sku, location_id, "bin_volume_capacity", "UNVERIFIED", modeled_volume, "unknown", "Location capacity is unavailable."))
            elif modeled_volume > capacity:
                results.append(_result(sku, location_id, "bin_volume_capacity", "VIOLATION", modeled_volume, capacity, "Modeled stock volume exceeds usable bin volume."))
        if weight is not None and weight > 0:
            load = weight * units
            capacity = _number(location.get("Max_Weight_Capacity_kg"))
            if capacity is None:
                results.append(_result(sku, location_id, "location_weight_capacity", "UNVERIFIED", load, "unknown", "Location capacity is unavailable."))
            elif load > capacity:
                results.append(_result(sku, location_id, "location_weight_capacity", "VIOLATION", load, capacity, "Modeled stock load exceeds location capacity."))

    ergonomics = config.get("ergonomics", {}) or {}
    threshold = _number(ergonomics.get("heavy_sku_weight_kg"))
    maximum_level = _number(ergonomics.get("max_shelf_level_for_heavy_skus"))
    level = _number(location.get("Shelf_Level"))
    if weight is not None and threshold is not None and maximum_level is not None and weight > threshold:
        if level is None:
            results.append(_result(sku, location_id, "ergonomic_shelf_height", "UNVERIFIED", "unknown", maximum_level, "Shelf level is unavailable."))
        elif level > maximum_level:
            results.append(_result(sku, location_id, "ergonomic_shelf_height", "VIOLATION", level, maximum_level, f"SKU weight {weight} kg exceeds configured threshold {threshold} kg."))

    for field in ("Hazard_Class", "Handling_Type"):
        value = product.get(field)
        if pd.isna(value) or value in ("", "UNSPECIFIED", "UNKNOWN"):
            results.append(_result(sku, location_id, field.lower(), "UNVERIFIED", value, "known attribute", "No safety-compliance conclusion can be made for this attribute."))
    for details in _known_incompatibility(product, config):
        results.append(_result(sku, location_id, "configured_incompatibility", "VIOLATION", details, "allowed combination", "Matches a configured incompatibility rule."))
    return results


def is_product_location_feasible(product: pd.Series, location: pd.Series, config: Mapping[str, Any] | None = None) -> bool:
    """Reject only known violations; unknown source attributes remain unverified."""
    return not any(result["Status"] == "VIOLATION" for result in product_location_results(product, location, config))


def validate_layout(layout: pd.DataFrame, skus: pd.DataFrame, locations: pd.DataFrame, config: Mapping[str, Any] | bool | None = None, allow_rotations: bool | None = None) -> pd.DataFrame:
    """Return structured known violations and unverified checks for an allocation."""
    config = _config(config, allow_rotations)
    results: list[dict[str, Any]] = []
    if layout.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    required = {"SKU_ID", "Location_ID"}
    missing = required - set(layout.columns)
    if missing:
        return pd.DataFrame([_result("", "", "layout_schema", "VIOLATION", sorted(missing), sorted(required), "Allocation is missing required reference columns.")], columns=RESULT_COLUMNS)
    products = skus.loc[~skus.SKU_ID.duplicated(keep=False)].set_index("SKU_ID", drop=False)
    locs = locations.loc[~locations.Location_ID.duplicated(keep=False)].set_index("Location_ID", drop=False)
    for sku in skus.loc[skus.SKU_ID.duplicated(keep=False), "SKU_ID"].dropna().unique():
        results.append(_result(sku, "", "duplicate_sku_master_record", "VIOLATION", sku, "unique SKU_ID", "SKU master contains duplicate identifiers."))
    for location_id in locations.loc[locations.Location_ID.duplicated(keep=False), "Location_ID"].dropna().unique():
        results.append(_result("", location_id, "duplicate_location_master_record", "VIOLATION", location_id, "unique Location_ID", "Location master contains duplicate identifiers."))
    for sku, group in layout.groupby("SKU_ID", dropna=False):
        if len(group) > 1:
            results.append(_result(sku, "", "assignment_uniqueness", "VIOLATION", len(group), 1, "A SKU is assigned more than once."))
    for location_id, group in layout.groupby("Location_ID", dropna=False):
        if len(group) > 1:
            results.append(_result("", location_id, "location_uniqueness", "VIOLATION", len(group), 1, "A location contains more than one SKU."))

    loads: list[dict[str, Any]] = []
    for sku, location_id in layout[["SKU_ID", "Location_ID"]].itertuples(index=False):
        sku_known, location_known = sku in products.index, location_id in locs.index
        if not sku_known:
            results.append(_result(sku, location_id, "sku_reference", "VIOLATION", sku, "known SKU_ID", "Assignment references an unknown SKU."))
        if not location_known:
            results.append(_result(sku, location_id, "location_reference", "VIOLATION", location_id, "known Location_ID", "Assignment references an unknown location."))
        if not (sku_known and location_known):
            continue
        product, location = products.loc[sku], locs.loc[location_id]
        results.extend(product_location_results(product, location, config))
        units, _, _ = _stock_units(product, config)
        weight = _number(product.get("Weight_kg"))
        if units is not None and weight is not None and weight > 0:
            loads.append({"SKU_ID": sku, "Rack_ID": location.get("Rack_ID"), "Bay": location.get("Bay"), "Shelf_Level": location.get("Shelf_Level"), "Load_kg": weight * units, "Shelf_Max_Load_kg": location.get("Shelf_Max_Load_kg"), "Rack_Max_Load_kg": location.get("Rack_Max_Load_kg")})
    if loads:
        load_frame = pd.DataFrame(loads)
        for key, group in load_frame.groupby(["Rack_ID", "Bay", "Shelf_Level"], dropna=False):
            limit, total = _number(group.iloc[0].Shelf_Max_Load_kg), float(group.Load_kg.sum())
            if limit is None:
                results.append(_result(",".join(group.SKU_ID), "", "aggregate_shelf_load", "UNVERIFIED", total, "unknown", f"Shelf {key} has no configured load limit."))
            elif total > limit:
                results.append(_result(",".join(group.SKU_ID), "", "aggregate_shelf_load", "VIOLATION", total, limit, f"Shelf {key} exceeds its configured aggregate load."))
        for rack_id, group in load_frame.groupby("Rack_ID", dropna=False):
            limit, total = _number(group.iloc[0].Rack_Max_Load_kg), float(group.Load_kg.sum())
            if limit is None:
                results.append(_result(",".join(group.SKU_ID), "", "aggregate_rack_load", "UNVERIFIED", total, "unknown", f"Rack {rack_id} has no configured load limit."))
            elif total > limit:
                results.append(_result(",".join(group.SKU_ID), "", "aggregate_rack_load", "VIOLATION", total, limit, f"Rack {rack_id} exceeds its configured aggregate load."))
    return pd.DataFrame(results, columns=RESULT_COLUMNS)
