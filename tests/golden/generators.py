"""Deterministic synthetic test fixture generators for all 7 corpus categories."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import openpyxl


def generate_flat_csv(output_path: Path) -> None:
    """Generate clean flat CSV golden fixture (Category: flat_csv_golden)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["TIMESTAMP", "ASSET_ID", "PRESSURE", "TEMPERATURE", "FLOW_RATE"])
        for i in range(1, 101):
            ts = f"2026-01-01T{i % 24:02d}:00:00Z"
            writer.writerow([ts, "COMP_1", round(10.5 + i * 0.1, 2), round(25.0 + i * 0.2, 2), 120])


def generate_excel_simple(output_path: Path) -> None:
    """Generate clean single-table XLSX (Category: excel_simple)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "SimpleReadings"

    headers = [
        "DATE",
        "TIME",
        "ASSET",
        "SUCTION_PRESS",
        "DISCHARGE_PRESS",
        "OIL_PRESS",
        "STAGE1_TEMP",
        "STAGE2_TEMP",
        "RPM",
    ]
    ws.append(headers)

    for i in range(1, 51):
        ws.append(
            [
                "2026-01-01",
                f"{i % 24:02d}:00:00",
                "COMP_A",
                2.5 + i * 0.05,
                15.0 + i * 0.1,
                4.2,
                45.0 + i * 0.2,
                65.0 + i * 0.3,
                1450,
            ]
        )

    wb.save(output_path)
    wb.close()


def generate_excel_complex(output_path: Path) -> None:
    """Generate multi-row merged headers with duplicate names (Category: excel_complex)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "MergedHeaders"

    # Row 1: Top-level equipment bands
    ws.merge_cells("B1:C1")
    ws["B1"] = "DISPENSER_1"
    ws.merge_cells("D1:E1")
    ws["D1"] = "DISPENSER_2"

    # Row 2: Sub-components
    ws["A2"] = "TIMESTAMP"
    ws["B2"] = "HOSE_A"
    ws["C2"] = "HOSE_B"
    ws["D2"] = "HOSE_A"
    ws["E2"] = "HOSE_B"

    # Row 3: Measurements (duplicate column names: PRESSURE, PRESSURE)
    ws["A3"] = "TIME_UTC"
    ws["B3"] = "PRESSURE"
    ws["C3"] = "TEMPERATURE"
    ws["D3"] = "PRESSURE"
    ws["E3"] = "TEMPERATURE"

    for r in range(4, 24):
        ws.append([f"2026-02-01T{r:02d}:00:00Z", 200 + r, 40 + r, 205 + r, 42 + r])

    wb.save(output_path)
    wb.close()


def generate_excel_scattered(output_path: Path) -> None:
    """Generate scattered layout with metadata block and data table (Category: excel_scattered)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "PlantReport"

    # Metadata block
    ws["A1"] = "Facility:"
    ws["B1"] = "Compressor Station 4"
    ws["A2"] = "Operator:"
    ws["B2"] = "AICONNEX Client"
    ws["A3"] = "Report Date:"
    ws["B3"] = "2026-03-01"

    # Main data table starting at row 6
    ws["A6"] = "TIMESTAMP"
    ws["B6"] = "SUCTION_P"
    ws["C6"] = "DISCHARGE_P"

    for r in range(7, 27):
        ws[f"A{r}"] = f"2026-03-01T{r:02d}:00:00Z"
        ws[f"B{r}"] = 5.2
        ws[f"C{r}"] = 22.8

    wb.save(output_path)
    wb.close()


def generate_excel_formula(output_path: Path) -> None:
    """Generate workbook with formula cells (Category: excel_formula)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Calculations"

    ws.append(["RAW_A", "RAW_B", "SUM_FORMULA"])
    for r in range(2, 22):
        ws.append([10 * r, 5 * r, f"=A{r}+B{r}"])

    wb.save(output_path)
    wb.close()


def generate_zip_mixed(output_path: Path) -> None:
    """Generate 5-file ZIP batch with 4 valid and 1 truncated workbook (zip_mixed)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 4 valid compressor workbooks
        for idx in range(1, 5):
            buf = io.BytesIO()
            wb = openpyxl.Workbook()
            ws = wb.active
            assert ws is not None
            ws.title = f"COMP_{idx}"
            ws.append(["TIMESTAMP", "PRESSURE", "TEMP"])
            for r in range(1, 21):
                ws.append([f"2026-04-01T{r:02d}:00:00Z", 100 + idx, 50])
            wb.save(buf)
            zf.writestr(f"compressor_log_{idx}.xlsx", buf.getvalue())

        # 1 truncated defective workbook (empty sheet, no headers)
        defective_buf = io.BytesIO()
        defective_wb = openpyxl.Workbook()
        defective_ws = defective_wb.active
        assert defective_ws is not None
        defective_ws.title = "CorruptSheet"
        defective_wb.save(defective_buf)
        zf.writestr("compressor_log_defective.xlsx", defective_buf.getvalue())


def generate_failure_cases(base_dir: Path) -> None:
    """Generate admission attack and corruption failure cases (Category: failure_cases)."""
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Path traversal ZIP
    traversal_path = base_dir / "traversal_attack.zip"
    with zipfile.ZipFile(traversal_path, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")

    # 2. Corrupted file
    corrupt_path = base_dir / "corrupted_signature.xlsx"
    corrupt_path.write_bytes(b"NOT_A_VALID_ZIP_OR_XLSX_HEADER_GARBAGE_PAYLOAD")


def generate_all_fixtures(root_fixtures_dir: Path) -> None:
    """Generate full test corpus across all 7 categories."""
    generate_flat_csv(root_fixtures_dir / "flat_csv_golden" / "compressor_golden.csv")
    generate_excel_simple(root_fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx")
    generate_excel_complex(root_fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx")
    generate_excel_scattered(root_fixtures_dir / "excel_scattered" / "scattered_with_metadata.xlsx")
    generate_excel_formula(root_fixtures_dir / "excel_formula" / "formula_stale_cache.xlsx")
    generate_zip_mixed(root_fixtures_dir / "zip_mixed" / "batch_5_compressors.zip")
    generate_failure_cases(root_fixtures_dir / "failure_cases")
