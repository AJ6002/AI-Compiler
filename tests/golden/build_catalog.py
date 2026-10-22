"""Build all synthetic corpus fixtures and write tests/golden/manifests/corpus_catalog.json."""

import hashlib
import json
from pathlib import Path

from src.compiler.contracts.enums import ErrorCode, JobResultState, UnitSource
from tests.golden.generators import generate_all_fixtures


def get_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    fixtures_dir = base_dir / "fixtures"
    manifests_dir = base_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic fixtures across all 7 corpus categories...")
    generate_all_fixtures(fixtures_dir)

    catalog_data = {
        "catalog_id": "catalog_v1_0_0",
        "schema_version": "1.0.0",
        "tenant_id": "tenant_test",
        "project_id": "project_test",
        "fixtures": [
            {
                "fixture_id": "fix_csv_01",
                "category": "flat_csv_golden",
                "relative_path": "flat_csv_golden/compressor_golden.csv",
                "sha256": get_sha256(fixtures_dir / "flat_csv_golden" / "compressor_golden.csv"),
                "is_synthetic": True,
                "expected_result_state": JobResultState.ACCEPTED,
                "expected_error_codes": [],
                "expected_sheet_names": [],
                "expected_row_count": 100,
                "expected_column_count": 5,
                "expected_signals": {
                    "PRESSURE": "COMP_1.PRESSURE",
                    "TEMPERATURE": "COMP_1.TEMPERATURE",
                    "FLOW_RATE": "COMP_1.FLOW_RATE",
                },
                "unit_sources": {
                    "PRESSURE": UnitSource.CLIENT_CONTRACT,
                    "TEMPERATURE": UnitSource.CLIENT_CONTRACT,
                    "FLOW_RATE": UnitSource.CLIENT_CONTRACT,
                },
                "expected_observation_count": 100,
            },
            {
                "fixture_id": "fix_excel_simple_01",
                "category": "excel_simple",
                "relative_path": "excel_simple/simple_table_ltds.xlsx",
                "sha256": get_sha256(fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"),
                "is_synthetic": True,
                "expected_result_state": JobResultState.ACCEPTED,
                "expected_error_codes": [],
                "expected_sheet_names": ["SimpleReadings"],
                "expected_row_count": 50,
                "expected_column_count": 9,
                "expected_signals": {
                    "SUCTION_PRESS": "COMP_A.SUCTION_PRESSURE",
                    "DISCHARGE_PRESS": "COMP_A.DISCHARGE_PRESSURE",
                },
                "unit_sources": {
                    "SUCTION_PRESS": UnitSource.HEADER_ROW,
                    "DISCHARGE_PRESS": UnitSource.HEADER_ROW,
                },
                "expected_observation_count": 50,
            },
            {
                "fixture_id": "fix_excel_complex_01",
                "category": "excel_complex",
                "relative_path": "excel_complex/merged_equipment_headers.xlsx",
                "sha256": get_sha256(
                    fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx"
                ),
                "is_synthetic": True,
                "expected_result_state": JobResultState.ACCEPTED,
                "expected_error_codes": [],
                "expected_sheet_names": ["MergedHeaders"],
                "expected_row_count": 20,
                "expected_column_count": 5,
                "expected_signals": {
                    "DISPENSER_1.HOSE_A.PRESSURE": "DISPENSER_1.HOSE_A.PRESSURE",
                    "DISPENSER_2.HOSE_A.PRESSURE": "DISPENSER_2.HOSE_A.PRESSURE",
                },
                "unit_sources": {
                    "DISPENSER_1.HOSE_A.PRESSURE": UnitSource.CLIENT_CONTRACT,
                    "DISPENSER_2.HOSE_A.PRESSURE": UnitSource.CLIENT_CONTRACT,
                },
                "expected_observation_count": 20,
            },
            {
                "fixture_id": "fix_excel_scattered_01",
                "category": "excel_scattered",
                "relative_path": "excel_scattered/scattered_with_metadata.xlsx",
                "sha256": get_sha256(
                    fixtures_dir / "excel_scattered" / "scattered_with_metadata.xlsx"
                ),
                "is_synthetic": True,
                "expected_result_state": JobResultState.ACCEPTED,
                "expected_error_codes": [],
                "expected_sheet_names": ["PlantReport"],
                "expected_row_count": 20,
                "expected_column_count": 3,
                "expected_signals": {
                    "SUCTION_P": "PLANT.SUCTION_P",
                    "DISCHARGE_P": "PLANT.DISCHARGE_P",
                },
                "unit_sources": {
                    "SUCTION_P": UnitSource.METADATA_BLOCK,
                    "DISCHARGE_P": UnitSource.METADATA_BLOCK,
                },
                "expected_observation_count": 20,
            },
            {
                "fixture_id": "fix_excel_formula_01",
                "category": "excel_formula",
                "relative_path": "excel_formula/formula_stale_cache.xlsx",
                "sha256": get_sha256(fixtures_dir / "excel_formula" / "formula_stale_cache.xlsx"),
                "is_synthetic": True,
                "expected_result_state": JobResultState.REVIEW_REQUIRED,
                "expected_error_codes": [ErrorCode.ERR_VAL_UNRESOLVED_UNIT],
                "expected_sheet_names": ["Calculations"],
                "expected_row_count": 20,
                "expected_column_count": 3,
                "expected_signals": {},
                "unit_sources": {},
                "expected_observation_count": 20,
            },
            {
                "fixture_id": "fix_zip_mixed_01",
                "category": "zip_mixed",
                "relative_path": "zip_mixed/batch_5_compressors.zip",
                "sha256": get_sha256(fixtures_dir / "zip_mixed" / "batch_5_compressors.zip"),
                "is_synthetic": True,
                "expected_result_state": JobResultState.REVIEW_REQUIRED,
                "expected_error_codes": [ErrorCode.ERR_STRUCT_MISSING_SHEET],
                "expected_sheet_names": ["COMP_1", "COMP_2", "COMP_3", "COMP_4"],
                "expected_row_count": 80,
                "expected_column_count": 3,
                "expected_signals": {},
                "unit_sources": {},
                "expected_observation_count": 80,
            },
            {
                "fixture_id": "fix_fail_traversal_01",
                "category": "failure_cases",
                "relative_path": "failure_cases/traversal_attack.zip",
                "sha256": get_sha256(fixtures_dir / "failure_cases" / "traversal_attack.zip"),
                "is_synthetic": True,
                "expected_result_state": JobResultState.FAILED,
                "expected_error_codes": [ErrorCode.ERR_ADM_PATH_TRAVERSAL],
                "expected_sheet_names": [],
                "expected_row_count": 0,
                "expected_column_count": 1,
                "expected_signals": {},
                "unit_sources": {},
                "expected_observation_count": 0,
            },
            {
                "fixture_id": "fix_fail_corrupt_02",
                "category": "failure_cases",
                "relative_path": "failure_cases/corrupted_signature.xlsx",
                "sha256": get_sha256(fixtures_dir / "failure_cases" / "corrupted_signature.xlsx"),
                "is_synthetic": True,
                "expected_result_state": JobResultState.FAILED,
                "expected_error_codes": [ErrorCode.ERR_ADM_FILE_CORRUPT],
                "expected_sheet_names": [],
                "expected_row_count": 0,
                "expected_column_count": 1,
                "expected_signals": {},
                "unit_sources": {},
                "expected_observation_count": 0,
            },
        ],
    }

    catalog_path = manifests_dir / "corpus_catalog.json"
    catalog_path.write_text(json.dumps(catalog_data, indent=2), encoding="utf-8")
    print(f"Master corpus catalog generated successfully at {catalog_path}")


if __name__ == "__main__":
    main()
