"""Unit tests for PlanExecutor on complex merged headers and duplicate column names."""

from pathlib import Path

import pytest

from src.compiler.execution.executor import PlanExecutor
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_executor_complex_merged_headers(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=25)

    discovery_engine = RuleBasedDiscoveryEngine()
    layout = discovery_engine.discover_sheet(structure.sheets[0])

    compiler = PlanCompiler()
    plan = compiler.compile(
        layout=layout,
        tenant_id="tenant-test",
        project_id="proj-test",
    )

    executor = PlanExecutor(reader=reader)
    result = executor.execute(xlsx_path, plan)

    # merged_equipment_headers has 20 data rows (rows 4 to 23) and 4 unpivoted signals
    assert result.reconciliation.data_rows_processed == 20
    assert result.reconciliation.signals_unpivoted == 4
    assert result.reconciliation.expected_emitted_records == 80
    assert result.reconciliation.actual_emitted_records == 80

    measurements = result.measurements_table
    signals_emitted = set(measurements.column("signal_id").to_pylist())

    # Verify duplicate leaf column names were disambiguated by hierarchical ancestors
    assert "DISPENSER_1.HOSE_A.PRESSURE" in signals_emitted
    assert "DISPENSER_1.HOSE_B.TEMPERATURE" in signals_emitted
    assert "DISPENSER_2.HOSE_A.PRESSURE" in signals_emitted
    assert "DISPENSER_2.HOSE_B.TEMPERATURE" in signals_emitted

    # Verify zero duplicate collision
    assert len(signals_emitted) == 4
