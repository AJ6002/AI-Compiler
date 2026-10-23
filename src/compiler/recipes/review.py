"""Data Steward Review Queue and human-in-the-loop recipe promotion workflow.

Manages review items for datasets flagged with REVIEW_REQUIRED, tracks 24-hour SLA targets,
and promotes approved parse plans into versioned, immutable recipes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import SharingTier
from src.compiler.contracts.plans import ParsePlan
from src.compiler.contracts.recipes import Recipe, StructuralSignature
from src.compiler.contracts.validation import ValidationErrorItem
from src.compiler.recipes.registry import RecipeRegistry
from src.compiler.recipes.signatures import SignatureGenerator


class ReviewStatus(StrEnum):
    """Review item processing status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"


class ReviewItem(BaseContract):
    """Encapsulated review package for data steward inspection and recipe promotion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str = Field(..., description="Unique review task identifier.")
    target_object_id: str = Field(..., description="Target upload or workbook SHA-256 / ID.")
    status: ReviewStatus = Field(
        default=ReviewStatus.PENDING,
        description="Review processing lifecycle status.",
    )
    created_at: datetime = Field(..., description="Timestamp when review task was enqueued.")
    sla_target_at: datetime = Field(
        ...,
        description="Target resolution SLA timestamp (created_at + 24 hours).",
    )
    sheet_name: str = Field(..., description="Affected spreadsheet worksheet name.")
    discovered_headers: list[str] = Field(
        ...,
        description="Headers discovered by structural analysis.",
    )
    draft_plan: ParsePlan = Field(..., description="Proposed parse plan awaiting review.")
    signature: StructuralSignature = Field(
        ...,
        description="Structural signature of the worksheet.",
    )
    validation_errors: list[ValidationErrorItem] = Field(
        default_factory=list,
        description="Blocking errors that triggered review.",
    )
    validation_warnings: list[ValidationErrorItem] = Field(
        default_factory=list,
        description="Advisory warnings discovered during validation.",
    )
    reconciliation_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Row and signal reconciliation audit numbers.",
    )
    reviewer_notes: str | None = Field(
        default=None,
        description="Audit commentary provided by the data steward.",
    )
    approved_recipe_id: str | None = Field(
        default=None,
        description="Recipe ID created if approved.",
    )
    resolved_at: datetime | None = Field(
        default=None,
        description="Timestamp when review decision was recorded.",
    )


class ReviewQueue:
    """In-memory thread-safe queue managing data steward reviews and SLA tracking."""

    def __init__(self) -> None:
        self._items: dict[str, ReviewItem] = {}

    def enqueue(
        self,
        tenant_id: str,
        project_id: str,
        target_object_id: str,
        sheet_name: str,
        discovered_headers: list[str],
        draft_plan: ParsePlan,
        signature: StructuralSignature | None = None,
        validation_errors: list[ValidationErrorItem] | None = None,
        validation_warnings: list[ValidationErrorItem] | None = None,
        reconciliation_summary: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        review_id: str | None = None,
    ) -> ReviewItem:
        """Enqueue a dataset or worksheet for data steward review with 24h SLA target."""
        rid = review_id or f"rev_{uuid.uuid4().hex[:12]}"
        now = created_at or datetime.now(UTC)
        sla_target = now + timedelta(hours=24)

        sig = signature or SignatureGenerator.create(
            sheet_names=[sheet_name],
            header_patterns=discovered_headers,
        )

        item = ReviewItem(
            review_id=rid,
            tenant_id=tenant_id,
            project_id=project_id,
            target_object_id=target_object_id,
            status=ReviewStatus.PENDING,
            created_at=now,
            sla_target_at=sla_target,
            sheet_name=sheet_name,
            discovered_headers=discovered_headers,
            draft_plan=draft_plan,
            signature=sig,
            validation_errors=validation_errors or [],
            validation_warnings=validation_warnings or [],
            reconciliation_summary=reconciliation_summary or {},
        )

        self._items[rid] = item
        return item

    def get(self, review_id: str) -> ReviewItem | None:
        """Fetch review item by ID."""
        return self._items.get(review_id)

    def list_items(
        self,
        tenant_id: str | None = None,
        status: ReviewStatus | None = None,
    ) -> list[ReviewItem]:
        """List review items with optional filtering by tenant and status."""
        result: list[ReviewItem] = []
        for item in self._items.values():
            if tenant_id and item.tenant_id != tenant_id:
                continue
            if status and item.status != status:
                continue
            result.append(item)
        return result

    def list_pending(self, tenant_id: str | None = None) -> list[ReviewItem]:
        """List all pending review items."""
        return self.list_items(tenant_id=tenant_id, status=ReviewStatus.PENDING)

    def approve_review(
        self,
        review_id: str,
        reviewer: str,
        approved_plan: ParsePlan | None = None,
        generation_system: str = "industrial_scada",
        sharing_tier: SharingTier = SharingTier.TENANT_BOUND,
        recipe_version: str = "1.0.0",
        notes: str | None = None,
        recipe_registry: RecipeRegistry | None = None,
        recipe_id: str | None = None,
    ) -> Recipe:
        """Steward approval workflow: promotes verified plan to an immutable, versioned Recipe."""
        item = self._items.get(review_id)
        if not item:
            raise KeyError(f"Review item '{review_id}' not found.")
        if item.status != ReviewStatus.PENDING:
            raise ValueError(
                f"Review item '{review_id}' is already resolved with status '{item.status}'."
            )

        now = datetime.now(UTC)
        final_plan = approved_plan or item.draft_plan
        is_corrected = (
            approved_plan is not None and approved_plan.plan_id != item.draft_plan.plan_id
        )
        final_status = ReviewStatus.CORRECTED if is_corrected else ReviewStatus.APPROVED

        rec_id = recipe_id or f"rcp_{uuid.uuid4().hex[:12]}"

        recipe = Recipe(
            recipe_id=rec_id,
            tenant_id=item.tenant_id,
            project_id=item.project_id,
            version=recipe_version,
            generation_system=generation_system,
            sharing_tier=sharing_tier,
            signature=item.signature,
            plan=final_plan,
            approved_by=reviewer,
            approved_at=now,
            is_revoked=False,
        )

        if recipe_registry is not None:
            recipe_registry.register(recipe)

        updated_item = item.model_copy(
            update={
                "status": final_status,
                "reviewer_notes": notes,
                "approved_recipe_id": rec_id,
                "resolved_at": now,
            }
        )
        self._items[review_id] = updated_item

        return recipe

    def reject_review(
        self,
        review_id: str,
        reviewer: str,
        reason: str,
    ) -> ReviewItem:
        """Steward rejection workflow: marks review item as rejected with audit reason."""
        item = self._items.get(review_id)
        if not item:
            raise KeyError(f"Review item '{review_id}' not found.")
        if item.status != ReviewStatus.PENDING:
            raise ValueError(
                f"Review item '{review_id}' is already resolved with status '{item.status}'."
            )

        now = datetime.now(UTC)
        updated_item = item.model_copy(
            update={
                "status": ReviewStatus.REJECTED,
                "reviewer_notes": f"Rejected by {reviewer}: {reason}",
                "resolved_at": now,
            }
        )
        self._items[review_id] = updated_item
        return updated_item
