import pandas as pd
import pytest

from src.operational_data import OperationalMetadataError, apply_operational_metadata


def _sku_master():
    return pd.DataFrame([
        {
            "SKU_ID": "sku-1",
            "Inventory_Units": pd.NA,
            "Hazard_Class": "UNSPECIFIED",
            "Handling_Type": "UNSPECIFIED",
        },
        {
            "SKU_ID": "sku-2",
            "Inventory_Units": pd.NA,
            "Hazard_Class": "UNSPECIFIED",
            "Handling_Type": "UNSPECIFIED",
        },
    ])


def _write_overlay(path, rows):
    pd.DataFrame(rows, columns=[
        "SKU_ID", "Inventory_Units", "Hazard_Class", "Handling_Type",
        "Inventory_Snapshot_At", "Inventory_Data_Source",
        "Safety_Verified_By", "Safety_Verified_At", "Safety_Data_Source",
    ]).to_csv(path, index=False)


def test_absent_overlay_preserves_unknown_values_and_reports_simulation_mode(tmp_path):
    master, audit = apply_operational_metadata(_sku_master(), tmp_path / "missing.csv")
    assert master["Inventory_Units"].isna().all()
    assert set(master["Hazard_Class"]) == {"UNSPECIFIED"}
    assert audit["overlay_found"] is False


def test_valid_operational_overlay_applies_values_and_provenance(tmp_path):
    path = tmp_path / "metadata.csv"
    _write_overlay(path, [{
        "SKU_ID": "sku-1",
        "Inventory_Units": 12,
        "Hazard_Class": "NONE",
        "Handling_Type": "NORMAL",
        "Inventory_Snapshot_At": "2026-10-27",
        "Inventory_Data_Source": "WMS stock export 2026-10-27",
        "Safety_Verified_By": "warehouse safety lead",
        "Safety_Verified_At": "2026-10-20",
        "Safety_Data_Source": "approved product safety register v3",
    }])
    master, audit = apply_operational_metadata(_sku_master(), path)
    row = master.set_index("SKU_ID").loc["sku-1"]
    assert float(row["Inventory_Units"]) == 12
    assert row["Hazard_Class"] == "NONE"
    assert row["Handling_Type"] == "NORMAL"
    assert row["Inventory_Data_Source"] == "WMS stock export 2026-10-27"
    assert pd.isna(master.set_index("SKU_ID").loc["sku-2", "Inventory_Units"])
    assert audit["inventory_values_applied"] == 1
    assert audit["safety_records_applied"] == 1


@pytest.mark.parametrize("quantity", [0, -1, 1.5, "not-a-number"])
def test_invalid_inventory_quantity_is_rejected(tmp_path, quantity):
    path = tmp_path / "metadata.csv"
    _write_overlay(path, [{
        "SKU_ID": "sku-1",
        "Inventory_Units": quantity,
        "Inventory_Snapshot_At": "2026-10-27",
        "Inventory_Data_Source": "WMS export",
    }])
    with pytest.raises(OperationalMetadataError, match="positive whole-number"):
        apply_operational_metadata(_sku_master(), path)


def test_inventory_without_snapshot_provenance_is_rejected(tmp_path):
    path = tmp_path / "metadata.csv"
    _write_overlay(path, [{"SKU_ID": "sku-1", "Inventory_Units": 4}])
    with pytest.raises(OperationalMetadataError, match="Inventory_Snapshot_At"):
        apply_operational_metadata(_sku_master(), path)


def test_safety_classification_without_review_provenance_is_rejected(tmp_path):
    path = tmp_path / "metadata.csv"
    _write_overlay(path, [{"SKU_ID": "sku-1", "Hazard_Class": "NONE", "Handling_Type": "NORMAL"}])
    with pytest.raises(OperationalMetadataError, match="Safety_Verified_By"):
        apply_operational_metadata(_sku_master(), path)


def test_unknown_skus_and_duplicate_skus_are_rejected(tmp_path):
    path = tmp_path / "metadata.csv"
    _write_overlay(path, [{"SKU_ID": "not-in-master", "Inventory_Units": 2,
                           "Inventory_Snapshot_At": "2026-10-27",
                           "Inventory_Data_Source": "WMS export"}])
    with pytest.raises(OperationalMetadataError, match="absent from the product master"):
        apply_operational_metadata(_sku_master(), path)

    _write_overlay(path, [{"SKU_ID": "sku-1"}, {"SKU_ID": "sku-1"}])
    with pytest.raises(OperationalMetadataError, match="Duplicate SKU_ID"):
        apply_operational_metadata(_sku_master(), path)
