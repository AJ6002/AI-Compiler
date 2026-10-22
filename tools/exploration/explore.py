"""Local Excel Exploration Workbench for data stewards and engineers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import openpyxl


def explore_sheet(sheet: openpyxl.worksheet.worksheet.Worksheet) -> dict[str, Any]:
    """Inspect structure, merged cells, headers, and data regions of a worksheet."""
    title = sheet.title
    max_row = sheet.max_row or 0
    max_column = sheet.max_column or 0

    merged_ranges = [str(m) for m in sheet.merged_cells.ranges]

    # Sample top rows for header detection
    sample_rows_limit = min(max_row, 30)
    row_types: list[dict[str, Any]] = []
    candidate_headers: list[int] = []
    duplicate_columns: dict[int, list[str]] = {}

    for r_idx in range(1, sample_rows_limit + 1):
        row_vals = [sheet.cell(row=r_idx, column=c_idx).value for c_idx in range(1, max_column + 1)]
        non_empty = [v for v in row_vals if v is not None and str(v).strip() != ""]
        if not non_empty:
            continue

        str_count = sum(1 for v in non_empty if isinstance(v, str))
        num_count = sum(1 for v in non_empty if isinstance(v, (int, float)))

        # Header candidate heuristic: majority strings
        if str_count >= len(non_empty) * 0.7 and len(non_empty) >= 2:
            candidate_headers.append(r_idx)
            # Check for duplicate column names
            str_names = [str(v).strip() for v in non_empty]
            dupes = [name for name in set(str_names) if str_names.count(name) > 1]
            if dupes:
                duplicate_columns[r_idx] = dupes

        row_types.append(
            {
                "row": r_idx,
                "non_empty": len(non_empty),
                "text_cells": str_count,
                "numeric_cells": num_count,
            }
        )

    # Candidate data regions
    data_start_row = candidate_headers[-1] + 1 if candidate_headers else 1

    # Generate draft recipe structure
    header_row_candidate = candidate_headers[-1] if candidate_headers else 1
    sample_header_cells = [
        str(sheet.cell(row=header_row_candidate, column=c_idx).value or f"col_{c_idx}").strip()
        for c_idx in range(1, min(max_column, 20) + 1)
        if sheet.cell(row=header_row_candidate, column=c_idx).value is not None
    ]

    draft_recipe = {
        "recipe_version": "1.0-draft",
        "sheet_name": title,
        "region": {
            "header_row": header_row_candidate,
            "data_start_row": data_start_row,
            "data_end_row": max_row,
            "max_columns": max_column,
        },
        "signals": sample_header_cells[:15],
    }

    return {
        "sheet_name": title,
        "dimensions": {
            "max_row": max_row,
            "max_column": max_column,
        },
        "merged_cell_count": len(merged_ranges),
        "merged_ranges_sample": merged_ranges[:10],
        "candidate_header_rows": candidate_headers,
        "duplicate_columns_in_headers": duplicate_columns,
        "candidate_data_start_row": data_start_row,
        "draft_recipe": draft_recipe,
    }


def explore_workbook(file_path: str | Path, target_sheet: str | None = None) -> dict[str, Any]:
    """Open workbook in read-only safe mode and extract structural summary."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Workbook file not found: {path}")

    # Note: data_only=False retains formula expressions while reading
    wb = openpyxl.load_workbook(path, read_only=False, data_only=False)
    sheet_names = wb.sheetnames

    results: dict[str, Any] = {
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "sheet_count": len(sheet_names),
        "sheet_names": sheet_names,
        "sheets": {},
    }

    sheets_to_process = [target_sheet] if target_sheet else sheet_names
    for name in sheets_to_process:
        if name in wb:
            results["sheets"][name] = explore_sheet(wb[name])

    wb.close()
    return results


def print_human_report(summary: dict[str, Any]) -> None:
    """Print readable terminal report for human steward."""
    print("=" * 70)
    print(f"WORKBOOK EXPLORATION: {summary['file_name']}")
    print(f"Total Sheets: {summary['sheet_count']} {summary['sheet_names']}")
    print("=" * 70)

    for sheet_name, sheet_data in summary["sheets"].items():
        dims = sheet_data["dimensions"]
        print(f"\n--- Sheet: '{sheet_name}' ---")
        print(f"  Dimensions: {dims['max_row']} rows x {dims['max_column']} cols")
        print(f"  Merged cell regions: {sheet_data['merged_cell_count']}")
        if sheet_data["merged_ranges_sample"]:
            print(f"    Sample merges: {', '.join(sheet_data['merged_ranges_sample'])}")
        print(f"  Candidate header rows: {sheet_data['candidate_header_rows']}")
        if sheet_data["duplicate_columns_in_headers"]:
            print("  WARNING: Duplicate column names detected in headers:")
            for r, dupes in sheet_data["duplicate_columns_in_headers"].items():
                print(f"    Row {r}: {dupes}")
        print(f"  Candidate data starts at row: {sheet_data['candidate_data_start_row']}")
        print("  Draft Recipe Preview:")
        print(f"    Header Row: {sheet_data['draft_recipe']['region']['header_row']}")
        print(f"    Sample Signals: {sheet_data['draft_recipe']['signals'][:6]}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="AICONNEX Excel Exploration Workbench")
    parser.add_argument("file", help="Path to Excel workbook (.xlsx)")
    parser.add_argument("--sheet", help="Target specific sheet name", default=None)
    parser.add_argument("--json", help="Output summary as JSON", action="store_true")

    args = parser.parse_args()

    try:
        summary = explore_workbook(args.file, target_sheet=args.sheet)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print_human_report(summary)
    except Exception as exc:
        print(f"Error exploring workbook: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
