"""Helper bridges translating InvestigationResult envelopes for executor and review queue.

Per ADR-015:
- unwrap_for_executor unpacks ParsePlan only when status is PLAN_PROPOSED.
- to_review_item adapts unresolved agent outcomes into ReviewItem packages for data stewards.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from src.compiler.contracts.enums import ErrorCode, ErrorSeverity, PlanOperationType
from src.compiler.contracts.investigation import InvestigationResult
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.contracts.validation import ValidationErrorItem
from src.compiler.recipes.review import ReviewItem, ReviewStatus
from src.compiler.recipes.signatures import SignatureGenerator


def unwrap_for_executor(result: InvestigationResult) -> ParsePlan:
    """Unwrap the proposed ParsePlan from an InvestigationResult for executor ingestion.

    Raises:
        ValueError: If result.status is not PLAN_PROPOSED or parse_plan is None.
    """
    if result.status != "PLAN_PROPOSED" or result.parse_plan is None:
        raise ValueError(
            f"Cannot unwrap ParsePlan from InvestigationResult with status '{result.status}'. "
            f"Status must be 'PLAN_PROPOSED' with a non-null parse_plan."
        )
    return result.parse_plan


def to_review_item(result: InvestigationResult, job_id: str) -> ReviewItem:
    """Convert an unresolved InvestigationResult into a domain ReviewItem for Data Stewards.

    Maps all UnresolvedIssue items to ValidationErrorItem instances, generates a provisional
    draft plan / signature, and embeds the agent's alternate hypotheses and evidence references.

    Raises:
        ValueError: If result.status is not REVIEW_REQUIRED.
    """
    if result.status != "REVIEW_REQUIRED":
        raise ValueError(f"to_review_item requires status 'REVIEW_REQUIRED', got '{result.status}'")

    first_sheet = result.unresolved[0].sheet if result.unresolved else "Sheet1"
    target_obj = result.unresolved[0].source_file if result.unresolved else job_id

    # Convert unresolved issues into blocking validation error items
    val_errors = [
        ValidationErrorItem(
            code=ErrorCode.ERR_STRUCT_AMBIGUOUS_HEADER,
            severity=ErrorSeverity.ERROR,
            message=issue.issue,
            sheet=issue.sheet,
            cell_coordinate=issue.cell_range,
            remediation=issue.required_clarification,
        )
        for issue in result.unresolved
    ]

    # If the agent proposed a partial plan, retain it; otherwise construct a safe fallback stub
    if result.parse_plan is not None:
        draft_plan = result.parse_plan
    else:
        draft_plan = ParsePlan(
            plan_id=f"plan_unresolved_{job_id}",
            tenant_id=result.tenant_id,
            project_id=result.project_id,
            target_sheet=first_sheet,
            operations=[
                PlanOperation(
                    op=PlanOperationType.FLATTEN_HEADERS,
                    params={"header_rows": [1]},
                )
            ],
        )

    sig = SignatureGenerator.create(
        sheet_names=[first_sheet],
        header_patterns=[],
    )

    now = datetime.now(UTC)
    sla_target = now + timedelta(hours=24)

    notes_parts = [f"Agent [{result.agent_id} v{result.agent_version}] flagged REVIEW_REQUIRED."]
    if result.alternate_interpretations_considered:
        notes_parts.append(
            "Alternates considered: " + "; ".join(result.alternate_interpretations_considered)
        )
    if result.evidence_references:
        notes_parts.append("Evidence references: " + str(result.evidence_references))

    return ReviewItem(
        review_id=f"rev_{uuid.uuid4().hex[:12]}",
        tenant_id=result.tenant_id,
        project_id=result.project_id,
        target_object_id=target_obj,
        status=ReviewStatus.PENDING,
        created_at=now,
        sla_target_at=sla_target,
        sheet_name=first_sheet,
        discovered_headers=[],
        draft_plan=draft_plan,
        signature=sig,
        validation_errors=val_errors,
        validation_warnings=[],
        reconciliation_summary={"job_id": job_id},
        reviewer_notes="\n".join(notes_parts),
    )
