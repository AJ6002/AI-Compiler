"""Unit tests for InvestigationResult and UnresolvedIssue contracts and helper bridges."""

import json

import pytest
from pydantic import ValidationError

from src.compiler.contracts.enums import PlanOperationType
from src.compiler.contracts.investigation import InvestigationResult, UnresolvedIssue
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.investigation.contract import to_review_item, unwrap_for_executor
from src.compiler.recipes.review import ReviewItem, ReviewStatus


def create_sample_plan() -> ParsePlan:
    return ParsePlan(
        plan_id="plan_sample_123",
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        target_sheet="Telemetry",
        operations=[
            PlanOperation(
                op=PlanOperationType.FLATTEN_HEADERS,
                params={"header_rows": [1]},
            )
        ],
        created_by="agent:claude-3-7-sonnet:1.0.0",
    )


def create_sample_issue() -> UnresolvedIssue:
    return UnresolvedIssue(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        issue="Ambiguous date format",
        source_file="telemetry.xlsx",
        sheet="Telemetry",
        cell_range="A3:A120",
        required_clarification="Confirm DD/MM/YYYY or MM/DD/YYYY.",
    )


def test_valid_plan_proposed_constructs() -> None:
    plan = create_sample_plan()
    result = InvestigationResult(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        status="PLAN_PROPOSED",
        parse_plan=plan,
        agent_id="claude-3-7-sonnet",
        agent_version="1.0.0",
        alternate_interpretations_considered=["Treat row 2 as secondary headers"],
        evidence_references={"A1:E2": "Header band detected via text density"},
    )

    assert result.status == "PLAN_PROPOSED"
    assert result.parse_plan == plan
    assert len(result.unresolved) == 0
    assert result.agent_id == "claude-3-7-sonnet"


def test_valid_review_required_constructs() -> None:
    issue = create_sample_issue()
    result = InvestigationResult(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        status="REVIEW_REQUIRED",
        parse_plan=None,
        unresolved=[issue],
        agent_id="claude-3-7-sonnet",
        agent_version="1.0.0",
    )

    assert result.status == "REVIEW_REQUIRED"
    assert result.parse_plan is None
    assert len(result.unresolved) == 1
    assert result.unresolved[0].issue == "Ambiguous date format"


def test_plan_proposed_with_none_plan_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        InvestigationResult(
            tenant_id="tenant_alpha",
            project_id="proj_beta",
            status="PLAN_PROPOSED",
            parse_plan=None,
            agent_id="claude-3-7-sonnet",
            agent_version="1.0.0",
        )
    assert "status 'PLAN_PROPOSED' requires a non-null parse_plan" in str(exc_info.value)


def test_review_required_with_plan_set_raises() -> None:
    plan = create_sample_plan()
    issue = create_sample_issue()
    with pytest.raises(ValidationError) as exc_info:
        InvestigationResult(
            tenant_id="tenant_alpha",
            project_id="proj_beta",
            status="REVIEW_REQUIRED",
            parse_plan=plan,
            unresolved=[issue],
            agent_id="claude-3-7-sonnet",
            agent_version="1.0.0",
        )
    assert "status 'REVIEW_REQUIRED' requires parse_plan to be None" in str(exc_info.value)


def test_review_required_with_empty_unresolved_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        InvestigationResult(
            tenant_id="tenant_alpha",
            project_id="proj_beta",
            status="REVIEW_REQUIRED",
            parse_plan=None,
            unresolved=[],
            agent_id="claude-3-7-sonnet",
            agent_version="1.0.0",
        )
    assert "requires at least one UnresolvedIssue" in str(exc_info.value)


def test_extra_fields_forbidden() -> None:
    plan = create_sample_plan()
    with pytest.raises(ValidationError) as exc_info:
        InvestigationResult(
            tenant_id="tenant_alpha",
            project_id="proj_beta",
            status="PLAN_PROPOSED",
            parse_plan=plan,
            agent_id="claude-3-7-sonnet",
            agent_version="1.0.0",
            hallucinated_extra_key="not_allowed",  # type: ignore[call-arg]
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_json_round_trip() -> None:
    plan = create_sample_plan()
    orig = InvestigationResult(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        status="PLAN_PROPOSED",
        parse_plan=plan,
        agent_id="claude-3-7-sonnet",
        agent_version="1.0.0",
        alternate_interpretations_considered=["Option A", "Option B"],
        evidence_references={"A1": "Cell has string timestamp"},
    )

    json_str = orig.model_dump_json()
    reconstructed = InvestigationResult.model_validate_json(json_str)

    assert reconstructed == orig
    assert reconstructed.parse_plan is not None
    assert reconstructed.parse_plan.plan_id == "plan_sample_123"
    assert reconstructed.alternate_interpretations_considered == ["Option A", "Option B"]
    assert reconstructed.evidence_references["A1"] == "Cell has string timestamp"


def test_unwrap_for_executor() -> None:
    plan = create_sample_plan()
    result_ok = InvestigationResult(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        status="PLAN_PROPOSED",
        parse_plan=plan,
        agent_id="claude-3-7-sonnet",
        agent_version="1.0.0",
    )

    unwrapped = unwrap_for_executor(result_ok)
    assert unwrapped == plan

    issue = create_sample_issue()
    result_err = InvestigationResult(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        status="REVIEW_REQUIRED",
        parse_plan=None,
        unresolved=[issue],
        agent_id="claude-3-7-sonnet",
        agent_version="1.0.0",
    )

    with pytest.raises(ValueError) as exc_info:
        unwrap_for_executor(result_err)
    assert "Cannot unwrap ParsePlan from InvestigationResult with status 'REVIEW_REQUIRED'" in str(
        exc_info.value
    )


def test_to_review_item() -> None:
    issue = create_sample_issue()
    result = InvestigationResult(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        status="REVIEW_REQUIRED",
        parse_plan=None,
        unresolved=[issue],
        agent_id="claude-3-7-sonnet",
        agent_version="1.0.0",
        alternate_interpretations_considered=["Hypothesis A", "Hypothesis B"],
        evidence_references={"A3": "Mixed format detected"},
    )

    review_item = to_review_item(result, job_id="job_789")

    assert isinstance(review_item, ReviewItem)
    assert review_item.tenant_id == "tenant_alpha"
    assert review_item.project_id == "proj_beta"
    assert review_item.sheet_name == "Telemetry"
    assert review_item.target_object_id == "telemetry.xlsx"
    assert review_item.status == ReviewStatus.PENDING
    assert len(review_item.validation_errors) == 1

    err = review_item.validation_errors[0]
    assert err.message == "Ambiguous date format"
    assert err.cell_coordinate == "A3:A120"
    assert err.remediation == "Confirm DD/MM/YYYY or MM/DD/YYYY."

    assert "Hypothesis A" in (review_item.reviewer_notes or "")
    assert "Evidence references" in (review_item.reviewer_notes or "")


def test_review_queue_accepts_review_item_directly() -> None:
    from src.compiler.recipes.review import ReviewQueue

    issue = create_sample_issue()
    result = InvestigationResult(
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        status="REVIEW_REQUIRED",
        parse_plan=None,
        unresolved=[issue],
        agent_id="claude-3-7-sonnet",
        agent_version="1.0.0",
    )

    review_item = to_review_item(result, job_id="job_queue_test")
    queue = ReviewQueue()
    queue._items[review_item.review_id] = review_item

    assert queue.get(review_item.review_id) is not None
    pending = queue.list_pending(tenant_id="tenant_alpha")
    assert len(pending) == 1
    assert pending[0].review_id == review_item.review_id
    assert pending[0].sheet_name == "Telemetry"


def test_parse_plan_created_by_round_trip() -> None:
    plan = ParsePlan(
        plan_id="plan_agent_origin",
        tenant_id="tenant_alpha",
        project_id="proj_beta",
        target_sheet="Telemetry",
        operations=[
            PlanOperation(
                op=PlanOperationType.FLATTEN_HEADERS,
                params={"header_rows": [1]},
            )
        ],
        created_by="agent:test",
    )

    assert plan.created_by == "agent:test"
    dumped = plan.model_dump_json()
    reloaded = ParsePlan.model_validate_json(dumped)
    assert reloaded.created_by == "agent:test"


def test_model_json_schema_validity() -> None:
    schema = InvestigationResult.model_json_schema()
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "status" in schema["properties"]
    assert "parse_plan" in schema["properties"]
    assert "unresolved" in schema["properties"]
    assert "agent_id" in schema["properties"]
    assert "agent_version" in schema["properties"]

    # Verify JSON serializability
    schema_json = json.dumps(schema)
    assert len(schema_json) > 0
