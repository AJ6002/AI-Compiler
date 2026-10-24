"""Durable workflow engine managing persistent job lifecycles and review wait-states."""

from __future__ import annotations

import datetime
import uuid

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import JobResultState
from src.compiler.contracts.plans import ParsePlan
from src.compiler.storage.object_store import ObjectStore
from src.compiler.workflows.activities import IngestionActivities
from src.compiler.workflows.errors import DeterministicSourceFault
from src.compiler.workflows.models import (
    CreateJobRequest,
    JobRecord,
    JobStatus,
    ReviewDecisionRequest,
)


class DurableWorkflowEngine:
    """In-process durable workflow engine executing sequential activities with state persistence."""

    def __init__(
        self,
        object_store: ObjectStore,
        activities: IngestionActivities | None = None,
    ) -> None:
        self.store = object_store
        self.activities = activities or IngestionActivities(object_store=self.store)
        self._jobs: dict[tuple[str, str, str], JobRecord] = {}
        self._idempotency_index: dict[str, str] = {}
        self._cached_inputs: dict[str, tuple[bytes, str]] = {}

    def create_job(
        self,
        tenant_id: str,
        project_id: str,
        request: CreateJobRequest,
    ) -> JobRecord:
        """Initialize a new ingestion job record, honoring idempotency keys."""
        if request.idempotency_key:
            idem_key = f"{tenant_id}:{project_id}:{request.idempotency_key}"
            if idem_key in self._idempotency_index:
                existing_id = self._idempotency_index[idem_key]
                return self._jobs[(tenant_id, project_id, existing_id)]

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.UTC)

        record = JobRecord(
            tenant_id=tenant_id,
            project_id=project_id,
            job_id=job_id,
            contract_id=request.contract_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            idempotency_key=request.idempotency_key,
        )

        self._jobs[(tenant_id, project_id, job_id)] = record
        if request.idempotency_key:
            self._idempotency_index[idem_key] = job_id

        return record

    def get_job(
        self,
        tenant_id: str,
        project_id: str,
        job_id: str,
    ) -> JobRecord | None:
        """Fetch job record enforcing strict tenant and project isolation."""
        return self._jobs.get((tenant_id, project_id, job_id))

    def list_jobs(
        self,
        tenant_id: str,
        project_id: str,
    ) -> list[JobRecord]:
        """List all jobs belonging to a specific tenant and project."""
        result: list[JobRecord] = []
        for (t, p, _), record in self._jobs.items():
            if t == tenant_id and p == project_id:
                result.append(record)
        return result

    def start_job(
        self,
        tenant_id: str,
        project_id: str,
        job_id: str,
        raw_bytes: bytes,
        filename: str,
        contract: ClientContract,
    ) -> JobRecord:
        """Execute ingestion workflow sequentially through deterministic activities."""
        job = self.get_job(tenant_id, project_id, job_id)
        if not job:
            raise KeyError(f"Job '{job_id}' not found for tenant '{tenant_id}'.")

        # Cache inputs for replay / resumption
        self._cached_inputs[job_id] = (raw_bytes, filename)

        # 1. Admission Activity
        job = job.model_copy(
            update={
                "status": JobStatus.PROCESSING,
                "current_stage": "admission",
                "updated_at": datetime.datetime.now(datetime.UTC),
            }
        )
        self._jobs[(tenant_id, project_id, job_id)] = job

        try:
            admission_result = self.activities.admission_activity(job, raw_bytes, filename)
            job = job.model_copy(
                update={
                    "upload_id": admission_result.object_id,
                    "current_stage": "discovery",
                }
            )

            # 2. Discovery Activity
            discoveries = self.activities.discovery_activity(job, admission_result)

            # 3. Plan Resolution Activity
            resolved = self.activities.plan_resolution_activity(job, discoveries)

            # Track any review items created during plan resolution
            review_ids: list[str] = list(job.review_item_ids)
            for _, _, _, _, r_item in resolved:
                if r_item and r_item.review_id not in review_ids:
                    review_ids.append(r_item.review_id)

            # 4. Execution & Validation Activity
            outcomes = self.activities.execution_and_validation_activity(job, contract, resolved)

            # Track any review items created during validation
            for pending in self.activities.review_queue.list_pending(tenant_id=job.tenant_id):
                if pending.review_id not in review_ids:
                    review_ids.append(pending.review_id)

            # 5. Batch Assembly & Publication Activity
            dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
            job = job.model_copy(update={"dataset_id": dataset_id})

            batch_result = self.activities.batch_publish_activity(job, contract, outcomes)

            final_status = (
                JobStatus.ACCEPTED
                if batch_result.result_state == JobResultState.ACCEPTED
                else JobStatus.REVIEW_REQUIRED
            )

            handoff_uri = f"{job.tenant_id}/{job.project_id}/published/{dataset_id}/handoff.json"
            val_uri = (
                f"{job.tenant_id}/{job.project_id}/published/{dataset_id}/validation-report.json"
            )

            job = job.model_copy(
                update={
                    "status": final_status,
                    "current_stage": "completed",
                    "updated_at": datetime.datetime.now(datetime.UTC),
                    "review_item_ids": review_ids,
                    "dataset_id": dataset_id,
                    "validation_report_uri": val_uri,
                    "handoff_manifest_uri": handoff_uri,
                }
            )
            self._jobs[(tenant_id, project_id, job_id)] = job
            return job

        except DeterministicSourceFault as e:
            job = job.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "error_message": str(e),
                    "updated_at": datetime.datetime.now(datetime.UTC),
                }
            )
            self._jobs[(tenant_id, project_id, job_id)] = job
            return job

    def resume_with_review_decision(
        self,
        tenant_id: str,
        project_id: str,
        job_id: str,
        review_id: str,
        decision: ReviewDecisionRequest,
        contract: ClientContract,
        corrected_plan: ParsePlan | None = None,
    ) -> JobRecord:
        """Process steward review decision, unblocking the review wait-state."""
        job = self.get_job(tenant_id, project_id, job_id)
        if not job:
            raise KeyError(f"Job '{job_id}' not found.")
        if job.status != JobStatus.REVIEW_REQUIRED:
            raise ValueError(
                f"Job '{job_id}' is not awaiting review (current status: {job.status})."
            )

        if decision.approved:
            # Promote plan to active recipe in registry
            self.activities.review_queue.approve_review(
                review_id=review_id,
                reviewer=decision.reviewer,
                approved_plan=corrected_plan,
                notes=decision.reason,
                recipe_registry=self.activities.recipe_registry,
            )

            # Replay job with newly promoted recipe
            if job_id in self._cached_inputs:
                raw_bytes, filename = self._cached_inputs[job_id]
                return self.start_job(tenant_id, project_id, job_id, raw_bytes, filename, contract)
        else:
            self.activities.review_queue.reject_review(
                review_id=review_id,
                reviewer=decision.reviewer,
                reason=decision.reason,
            )
            job = job.model_copy(
                update={
                    "status": JobStatus.REJECTED,
                    "error_message": f"Rejected by steward: {decision.reason}",
                    "updated_at": datetime.datetime.now(datetime.UTC),
                }
            )
            self._jobs[(tenant_id, project_id, job_id)] = job

        return job
