import pytest
from pydantic import ValidationError

from src.compiler.contracts import (
    AssetMap,
    JobExecutionState,
    ObservationId,
    PlanOperation,
    ValidationReport,
)


def test_extra_fields_forbidden():
    """Verify that extra fields are rejected to prevent payload injection."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ObservationId(
            tenant_id="t1",
            project_id="p1",
            asset_id="a1",
            raw_source_row=10,
            source_file="file.xlsx",
            injected_payload="evil_code",  # Extra field
        )


def test_missing_scope_forbidden():
    """Verify that tenant_id and project_id are strictly mandatory."""
    with pytest.raises(ValidationError) as exc_info:
        AssetMap(
            map_id="m1",
            version="1.0.0",
            mappings={"tag": "asset"},
            # Missing tenant_id and project_id
        )
    errors = exc_info.value.errors()
    missing_fields = {e["loc"][0] for e in errors if e["type"] == "missing"}
    assert "tenant_id" in missing_fields
    assert "project_id" in missing_fields


def test_immutability_enforced():
    """Verify that contracts are frozen and cannot be mutated post-initialization."""
    obs = ObservationId(
        tenant_id="t1",
        project_id="p1",
        asset_id="a1",
        raw_source_row=10,
        source_file="file.xlsx",
    )
    with pytest.raises(ValidationError):
        obs.asset_id = "a2"  # Attempt to mutate frozen model


def test_state_segregation():
    """Verify that execution states cannot be passed into result state fields."""
    with pytest.raises(ValidationError):
        ValidationReport(
            tenant_id="t1",
            project_id="p1",
            report_id="r1",
            target_object_id="obj1",
            result_state=JobExecutionState.EXECUTING,  # Execution state rejected
        )


def test_allowlisted_operations_only():
    """Verify that unknown plan operations are rejected."""
    with pytest.raises(ValidationError):
        PlanOperation(
            op="arbitrary_python_eval",  # Disallowed operation
            params={},
        )
