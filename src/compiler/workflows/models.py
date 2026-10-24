"""Workflow domain models, DTOs, and event contracts for Phase 10."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import JobResultState


class JobStatus(StrEnum):
    """Lifecycle state of an ingestion job."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CreateJobRequest(BaseModel):
    """Request payload to initialize an ingestion job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str = Field(..., description="Target ClientContract identifier")
    description: str | None = Field(default=None, description="Optional job notes")
    idempotency_key: str | None = Field(default=None, description="Client idempotency key")


class JobResponse(BaseModel):
    """Caller-visible status and artifacts of an ingestion job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    tenant_id: str
    project_id: str
    contract_id: str
    status: JobStatus
    upload_id: str | None = None
    created_at: datetime
    updated_at: datetime
    dataset_id: str | None = None
    error_message: str | None = None
    validation_report_uri: str | None = None
    handoff_manifest_uri: str | None = None
    review_item_ids: list[str] = Field(default_factory=list)


class ReviewDecisionRequest(BaseModel):
    """Steward approval or rejection decision unblocking a review wait-state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approved: bool = Field(..., description="True to approve/clear, False to reject")
    reviewer: str = Field(..., description="Steward username or email")
    reason: str = Field(..., min_length=3, description="Audit justification")
    corrected_plan_id: str | None = Field(default=None, description="Optional override plan ID")


class HandoffEvent(BaseModel):
    """Authenticated event emitted to outbox upon dataset publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    job_id: str
    tenant_id: str
    project_id: str
    dataset_id: str
    result_state: JobResultState
    handoff_manifest_uri: str
    payload_sha256: str
    emitted_at: datetime
    delivered: bool = False


class JobRecord(BaseContract):
    """Internal persistent state representation for a durable workflow job."""

    job_id: str
    contract_id: str
    status: JobStatus = JobStatus.PENDING
    upload_id: str | None = None
    dataset_id: str | None = None
    created_at: datetime
    updated_at: datetime
    current_stage: str = "initialized"
    stage_outputs: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    error_message: str | None = None
    review_item_ids: list[str] = Field(default_factory=list)
    validation_report_uri: str | None = None
    handoff_manifest_uri: str | None = None
