"""Integration tests verifying PlanValidator against golden fixtures and corpus workbooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.compiler.contracts.enums import JobResultState
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers import get_reader
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine
from src.compiler.validation.plan_validator import PlanValidator


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "golden" / "fixtures"


def test_golden_corpus_simple_table_validation(fixtures_dir: Path):
    """Assert cleanly discovered layouts on simple_table_ltds.xlsx pass 3-level validation."""
    fixture_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    assert fixture_path.exists()

    reader = get_reader()
    structure = reader.inspect(
        source=fixture_path,
        tenant_id="tenant_oil_gas",
        project_id="proj_station_4",
        workbook_name="simple_table_ltds.xlsx",
    )
    discovery = RuleBasedDiscoveryEngine()
    compiler = PlanCompiler()
    validator = PlanValidator()

    layout = discovery.discover_sheet(structure.sheets[0])
    assert layout.verdict == JobResultState.ACCEPTED

    plan = compiler.compile(
        layout=layout,
        tenant_id="tenant_oil_gas",
        project_id="proj_station_4",
        default_asset_id=layout.sheet_name,
    )

    rep = validator.validate(
        plan=plan,
        source=fixture_path,
        layout=layout,
        source_filename="simple_table_ltds.xlsx",
        default_asset_id=layout.sheet_name,
    )

    assert rep.status == JobResultState.ACCEPTED
    assert rep.schema_passed is True
    assert rep.semantics_passed is True
    assert rep.evidence_passed is True
    assert len(rep.issues) == 0


def test_golden_corpus_complex_merged_headers_validation(fixtures_dir: Path):
    """Assert merged_equipment_headers.xlsx compiles and validates through PlanValidator."""
    fixture_path = fixtures_dir / "excel_complex" / "merged_equipment_headers.xlsx"
    assert fixture_path.exists()

    reader = get_reader()
    structure = reader.inspect(
        source=fixture_path,
        tenant_id="tenant_gen",
        project_id="proj_power",
        workbook_name="merged_equipment_headers.xlsx",
    )
    discovery = RuleBasedDiscoveryEngine()
    compiler = PlanCompiler()
    validator = PlanValidator()

    layout = discovery.discover_sheet(structure.sheets[0])

    for idx in range(len(layout.tables)):
        plan = compiler.compile(
            layout=layout,
            tenant_id="tenant_gen",
            project_id="proj_power",
            table_index=idx,
            default_asset_id=layout.sheet_name,
        )

        rep = validator.validate(
            plan=plan,
            source=fixture_path,
            layout=layout,
            source_filename="merged_equipment_headers.xlsx",
            default_asset_id=layout.sheet_name,
        )

        assert rep.schema_passed is True
        assert rep.semantics_passed is True
        assert rep.evidence_passed is True
        assert rep.status == JobResultState.ACCEPTED
