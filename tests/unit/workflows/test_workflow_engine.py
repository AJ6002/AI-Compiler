"""Unit tests for DurableWorkflowEngine, tenant isolation, and outbox event delivery."""

from datetime import UTC, datetime

import pytest

from src.compiler.contracts.enums import JobResultState
from src.compiler.storage.object_store import LocalFileSystemObjectStore
from src.compiler.workflows.engine import DurableWorkflowEngine
from src.compiler.workflows.models import (
    CreateJobRequest,
    HandoffEvent,
    JobStatus,
)
from src.compiler.workflows.outbox import HandoffOutbox


@pytest.fixture
def temp_store(tmp_path) -> LocalFileSystemObjectStore:
    return LocalFileSystemObjectStore(tmp_path)


def test_job_lifecycle_create_and_idempotency(temp_store):
    """Verify job creation and idempotency key deduplication."""
    engine = DurableWorkflowEngine(object_store=temp_store)

    req1 = CreateJobRequest(contract_id="contract_fleet", idempotency_key="key_12345")
    job1 = engine.create_job(tenant_id="tenant_a", project_id="proj_1", request=req1)

    assert job1.job_id.startswith("job_")
    assert job1.status == JobStatus.PENDING
    assert job1.contract_id == "contract_fleet"

    # Submitting identical idempotency key returns existing job
    req2 = CreateJobRequest(contract_id="contract_fleet", idempotency_key="key_12345")
    job2 = engine.create_job(tenant_id="tenant_a", project_id="proj_1", request=req2)

    assert job2.job_id == job1.job_id


def test_job_tenant_isolation(temp_store):
    """Verify Tenant B cannot lookup or access Tenant A's jobs."""
    engine = DurableWorkflowEngine(object_store=temp_store)

    req = CreateJobRequest(contract_id="contract_fleet")
    job_a = engine.create_job(tenant_id="tenant_a", project_id="proj_1", request=req)

    # Tenant B lookup returns None
    assert engine.get_job("tenant_b", "proj_1", job_a.job_id) is None

    # Mismatched project lookup returns None
    assert engine.get_job("tenant_a", "proj_other", job_a.job_id) is None


def test_outbox_emit_and_deduplication():
    """Verify outbox emits events and deduplicates duplicate publications."""
    outbox = HandoffOutbox()
    now = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)

    event1 = HandoffEvent(
        event_id="evt_1",
        job_id="job_1",
        tenant_id="tenant_a",
        project_id="proj_1",
        dataset_id="ds_1",
        result_state=JobResultState.ACCEPTED,
        handoff_manifest_uri="path/to/handoff.json",
        payload_sha256="abc123sha",
        emitted_at=now,
        delivered=False,
    )

    emitted1 = outbox.emit(event1)
    assert emitted1.event_id == "evt_1"
    assert len(outbox.list_pending()) == 1

    # Emitting with identical handoff uri and payload sha returns original event
    event2 = HandoffEvent(
        event_id="evt_2",
        job_id="job_1",
        tenant_id="tenant_a",
        project_id="proj_1",
        dataset_id="ds_1",
        result_state=JobResultState.ACCEPTED,
        handoff_manifest_uri="path/to/handoff.json",
        payload_sha256="abc123sha",
        emitted_at=now,
        delivered=False,
    )
    emitted2 = outbox.emit(event2)
    assert emitted2.event_id == "evt_1"
    assert len(outbox.list_all()) == 1

    # Mark delivered
    outbox.mark_delivered("evt_1")
    assert len(outbox.list_pending()) == 0
