"""Unit tests for ReviewQueue, SLA tracking, steward approval, and recipe promotion."""

from datetime import UTC, datetime, timedelta

import pytest

from src.compiler.contracts.enums import ErrorCode, ErrorSeverity, PlanOperationType, SharingTier
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.contracts.validation import ValidationErrorItem
from src.compiler.recipes.registry import RecipeRegistry
from src.compiler.recipes.review import ReviewQueue, ReviewStatus


def _make_dummy_plan(plan_id: str, tenant_id: str) -> ParsePlan:
    return ParsePlan(
        tenant_id=tenant_id,
        project_id="proj_1",
        plan_id=plan_id,
        target_sheet="Sheet1",
        operations=[
            PlanOperation(op=PlanOperationType.SELECT_REGION, params={"min_row": 1, "max_row": 100})
        ],
    )


def test_enqueue_review_item_with_24h_sla():
    """Verify that enqueued review items compute SLA target at created_at + 24 hours."""
    queue = ReviewQueue()
    now = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
    plan = _make_dummy_plan("plan_test", "tenant_a")

    item = queue.enqueue(
        tenant_id="tenant_a",
        project_id="proj_1",
        target_object_id="obj_sha_123",
        sheet_name="Sheet1",
        discovered_headers=["TIMESTAMP", "PRESS", "TEMP"],
        draft_plan=plan,
        validation_errors=[
            ValidationErrorItem(
                code=ErrorCode.ERR_STRUCT_AMBIGUOUS_HEADER,
                severity=ErrorSeverity.ERROR,
                message="Ambiguous header row detected",
                sheet="Sheet1",
                remediation="Steward inspection required",
            )
        ],
        created_at=now,
    )

    assert item.status == ReviewStatus.PENDING
    assert item.created_at == now
    expected_sla = now + timedelta(hours=24)
    assert item.sla_target_at == expected_sla
    assert len(item.validation_errors) == 1

    # Fetch from queue
    fetched = queue.get(item.review_id)
    assert fetched is not None
    assert fetched.review_id == item.review_id


def test_steward_approval_creates_and_registers_recipe():
    """Steward approval promotes draft plan to an active, versioned Recipe in the registry."""
    queue = ReviewQueue()
    registry = RecipeRegistry()
    now = datetime.now(UTC)
    plan = _make_dummy_plan("draft_plan_1", "tenant_a")

    item = queue.enqueue(
        tenant_id="tenant_a",
        project_id="proj_1",
        target_object_id="obj_sha_456",
        sheet_name="CompressorData",
        discovered_headers=["TIME", "RPM", "TORQUE"],
        draft_plan=plan,
        created_at=now,
    )

    recipe = queue.approve_review(
        review_id=item.review_id,
        reviewer="senior_steward@aiconnex.com",
        recipe_registry=registry,
        notes="Verified column alignment with compressor plant layout.",
        generation_system="siemens_scada",
        sharing_tier=SharingTier.TENANT_BOUND,
        recipe_version="1.0.0",
    )

    assert recipe.recipe_id.startswith("rcp_")
    assert recipe.version == "1.0.0"
    assert recipe.approved_by == "senior_steward@aiconnex.com"
    assert recipe.generation_system == "siemens_scada"
    assert not recipe.is_revoked

    # Verify review item state updated
    updated_item = queue.get(item.review_id)
    assert updated_item is not None
    assert updated_item.status == ReviewStatus.APPROVED
    assert updated_item.approved_recipe_id == recipe.recipe_id
    assert updated_item.resolved_at is not None

    # Verify recipe is now queryable via registry lookup
    matched = registry.lookup("tenant_a", recipe.signature)
    assert matched is not None
    assert matched.recipe_id == recipe.recipe_id


def test_steward_approval_with_corrected_plan():
    """If steward supplies a modified plan, status becomes CORRECTED."""
    queue = ReviewQueue()
    draft_plan = _make_dummy_plan("draft_1", "tenant_a")
    corrected_plan = _make_dummy_plan("corrected_1", "tenant_a")

    item = queue.enqueue(
        tenant_id="tenant_a",
        project_id="proj_1",
        target_object_id="obj_sha_789",
        sheet_name="Sheet1",
        discovered_headers=["A", "B"],
        draft_plan=draft_plan,
    )

    recipe = queue.approve_review(
        review_id=item.review_id,
        reviewer="steward@aiconnex.com",
        approved_plan=corrected_plan,
        notes="Adjusted data start row offset.",
    )

    updated_item = queue.get(item.review_id)
    assert updated_item is not None
    assert updated_item.status == ReviewStatus.CORRECTED
    assert recipe.plan.plan_id == "corrected_1"


def test_steward_rejection_workflow():
    """Steward rejection marks item REJECTED with clear reason."""
    queue = ReviewQueue()
    plan = _make_dummy_plan("plan_reject", "tenant_a")

    item = queue.enqueue(
        tenant_id="tenant_a",
        project_id="proj_1",
        target_object_id="obj_sha_bad",
        sheet_name="CorruptSheet",
        discovered_headers=["UNKNOWN"],
        draft_plan=plan,
    )

    rejected_item = queue.reject_review(
        review_id=item.review_id,
        reviewer="lead_auditor@aiconnex.com",
        reason="Workbook contains corrupted, unrecoverable binary payload.",
    )

    assert rejected_item.status == ReviewStatus.REJECTED
    assert "corrupted, unrecoverable" in rejected_item.reviewer_notes
    assert rejected_item.resolved_at is not None
    assert rejected_item.approved_recipe_id is None


def test_cannot_resolve_already_resolved_review():
    """Attempting to approve or reject a resolved item raises ValueError."""
    queue = ReviewQueue()
    plan = _make_dummy_plan("plan_once", "tenant_a")
    item = queue.enqueue(
        tenant_id="tenant_a",
        project_id="proj_1",
        target_object_id="obj_1",
        sheet_name="S1",
        discovered_headers=["A"],
        draft_plan=plan,
    )

    queue.approve_review(review_id=item.review_id, reviewer="rev1")

    with pytest.raises(ValueError, match="already resolved"):
        queue.approve_review(review_id=item.review_id, reviewer="rev2")

    with pytest.raises(ValueError, match="already resolved"):
        queue.reject_review(review_id=item.review_id, reviewer="rev2", reason="late")
