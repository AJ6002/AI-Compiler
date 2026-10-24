"""Contracts for the investigation layer returned by the agent supervisor.

Governed by ADR-015:
- Wraps ParsePlan in an immutable envelope rather than polluting ParsePlan with audit fields.
- Provides explicit rejections (REVIEW_REQUIRED) with detailed UnresolvedIssue items.
- Retains alternative interpretations considered and evidence references for auditability.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.plans import ParsePlan


class UnresolvedIssue(BaseContract):
    """Specific structural or semantic ambiguity that prevented automated plan generation."""

    tenant_id: str = Field(default="system", description="Tenant identity scoping this issue.")
    project_id: str = Field(default="system", description="Project identifier scoping this issue.")
    issue: str = Field(..., description="High-level description of the ambiguity encountered.")
    source_file: str = Field(..., description="Source workbook filename where ambiguity was found.")
    sheet: str = Field(..., description="Specific worksheet name where ambiguity was found.")
    cell_range: str = Field(..., description="A1-notation cell coordinate or range of the issue.")
    required_clarification: str = Field(
        ...,
        description="Prescribed clarification requested from the human data steward.",
    )


class InvestigationResult(BaseContract):
    """Enveloped output emitted by the agentic investigation layer."""

    tenant_id: str = Field(default="system", description="Tenant identity scoping this result.")
    project_id: str = Field(default="system", description="Project identifier scoping this result.")
    schema_version: str = Field(default="1.0.0", description="Contract schema version.")
    status: Literal["PLAN_PROPOSED", "REVIEW_REQUIRED"] = Field(
        ...,
        description="Investigation verdict: plan ready for dry-run or steward review needed.",
    )
    parse_plan: ParsePlan | None = Field(
        default=None,
        description="Proposed deterministic ParsePlan if status is PLAN_PROPOSED.",
    )
    unresolved: list[UnresolvedIssue] = Field(
        default_factory=list,
        description="List of blocking ambiguities explaining why human review is required.",
    )

    # Audit-only fields — not consumed by executor
    alternate_interpretations_considered: list[str] = Field(
        default_factory=list,
        description="Hypotheses or layout options considered and rejected during investigation.",
    )
    evidence_references: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of observations or cell coordinates to rationale/proof.",
    )
    agent_id: str = Field(
        ...,
        description="Identity of the agent/model that conducted the investigation.",
    )
    agent_version: str = Field(
        ...,
        description="Version string of the agent investigation harness.",
    )

    @model_validator(mode="after")
    def validate_status_and_plan(self) -> Self:
        """Enforce strict cross-field invariants between status, parse_plan, and unresolved."""
        if self.status == "PLAN_PROPOSED":
            if self.parse_plan is None:
                raise ValueError("status 'PLAN_PROPOSED' requires a non-null parse_plan")
        elif self.status == "REVIEW_REQUIRED":
            if self.parse_plan is not None:
                raise ValueError("status 'REVIEW_REQUIRED' requires parse_plan to be None")
            if not self.unresolved:
                raise ValueError("status 'REVIEW_REQUIRED' requires at least one UnresolvedIssue")
        return self
