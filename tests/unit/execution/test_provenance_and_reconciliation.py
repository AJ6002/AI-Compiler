"""Unit tests for ProvenanceTracker and formula handling in PlanExecutor."""

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.compiler.execution.executor import PlanExecutor
from src.compiler.execution.provenance import (
    PROVENANCE_ARROW_SCHEMA,
    ProvenanceTracker,
)
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


def test_provenance_tracker_arrow_and_parquet(tmp_path: Path) -> None:
    tracker = ProvenanceTracker()
    tracker.record(
        observation_key="obs_12345",
        signal_id="STAGE_1.PRESSURE",
        source_file="unit1.xlsx",
        sheet_name="Readings",
        cell_coordinate="B10",
        raw_value=105.2,
        formula=None,
    )

    table = tracker.to_arrow()
    assert table.schema.equals(PROVENANCE_ARROW_SCHEMA)
    assert table.num_rows == 1

    pq_path = tmp_path / "source-map.parquet"
    tracker.write_parquet(pq_path)
    assert pq_path.is_file()

    read_back = pq.read_table(pq_path)
    assert read_back.num_rows == 1
    assert read_back.column("cell_coordinate")[0].as_py() == "B10"


def test_executor_formula_policy_require_literal_only(fixtures_dir: Path) -> None:
    xlsx_path = fixtures_dir / "excel_formula" / "formula_stale_cache.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-test", "proj-test", max_preview_rows=15)

    discovery_engine = RuleBasedDiscoveryEngine()
    layout = discovery_engine.discover_sheet(structure.sheets[0])

    compiler = PlanCompiler()
    # Require literal only -> formula cells must raise ValueError
    plan = compiler.compile(
        layout=layout,
        tenant_id="tenant-test",
        project_id="proj-test",
        formula_policy="require_literal_only",
    )

    executor = PlanExecutor(reader=reader)
    with pytest.raises(ValueError, match="rejected under require_literal_only policy"):
        executor.execute(xlsx_path, plan)
