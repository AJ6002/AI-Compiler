"""Unit tests for PlanExecutor on simple tabular workbooks."""

from pathlib import Path

import pyarrow as pa
import pytest

from src.compiler.execution.executor import MEASUREMENT_ARROW_SCHEMA, PlanExecutor
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_executor_simple_table_ltds(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=15)

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

    # Verify reconciliation metrics
    # simple_table_ltds has 50 data rows and 6 numeric signals
    # (SUCTION_PRESS, DISCHARGE_PRESS, OIL_PRESS, STAGE1_TEMP, STAGE2_TEMP, RPM)
    assert result.reconciliation.data_rows_processed == 50
    assert result.reconciliation.signals_unpivoted == 6
    assert result.reconciliation.expected_emitted_records == 300
    assert result.reconciliation.actual_emitted_records == 300
    assert result.reconciliation.reconciliation_hash != ""

    # Verify Arrow Table schemas and records
    measurements = result.measurements_table
    assert measurements.schema.equals(MEASUREMENT_ARROW_SCHEMA)
    assert measurements.num_rows == 300

    # Verify observation keys are populated and SHA-256 length (64 chars)
    obs_col = measurements.column("observation_key").to_pylist()
    assert all(len(k) == 64 for k in obs_col)

    # Verify asset column contains COMP_A from the spreadsheet
    asset_col = set(measurements.column("asset_id").to_pylist())
    assert "COMP_A" in asset_col

    # Verify timestamps are UTC timestamps
    ts_col = measurements.column("timestamp_utc")
    assert pa.types.is_timestamp(ts_col.type)

    # Verify provenance table
    prov = result.provenance_table
    assert prov.num_rows == 300
    sig_set = set(prov.column("signal_id").to_pylist())
    assert "SUCTION_PRESS" in sig_set
    assert "RPM" in sig_set
