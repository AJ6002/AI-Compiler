"""API endpoints for job lifecycle, durable workflow execution, and steward review."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Header, HTTPException, Response, UploadFile, status

from apps.api.config import settings
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import PartialBatchPolicy
from src.compiler.recipes.review import ReviewItem
from src.compiler.storage.object_store import LocalFileSystemObjectStore
from src.compiler.workflows.engine import DurableWorkflowEngine
from src.compiler.workflows.models import (
    CreateJobRequest,
    JobRecord,
    JobResponse,
    ReviewDecisionRequest,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Default storage and engine initialization
_storage = LocalFileSystemObjectStore(settings.local_storage_root)
_engine = DurableWorkflowEngine(object_store=_storage)

# Registered client contracts catalogue
_contracts: dict[str, ClientContract] = {}


def register_contract(contract: ClientContract) -> None:
    """Register client contract into the control plane catalogue."""
    _contracts[contract.contract_id] = contract


# Register default fleet contract
register_contract(
    ClientContract(
        contract_id="contract_compressor_fleet",
        tenant_id="tenant_oil_gas",
        project_id="proj_station_4",
        version="1.0.0",
        expected_assets=["COMP_1", "COMP_2", "COMP_3", "COMP_4"],
        required_signals=["PRESSURE", "TEMP"],
        allowed_units={"PRESSURE": ["bar", "psi"], "TEMP": ["C", "F"]},
        timezone="UTC",
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )
)


def _to_response(record: JobRecord) -> JobResponse:
    return JobResponse(
        job_id=record.job_id,
        tenant_id=record.tenant_id,
        project_id=record.project_id,
        contract_id=record.contract_id,
        status=record.status,
        upload_id=record.upload_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        dataset_id=record.dataset_id,
        error_message=record.error_message,
        validation_report_uri=record.validation_report_uri,
        handoff_manifest_uri=record.handoff_manifest_uri,
        review_item_ids=record.review_item_ids,
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ingestion job.",
)
async def create_job(
    request: CreateJobRequest,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_project_id: Annotated[str, Header(alias="X-Project-ID")],
) -> JobResponse:
    """Initialize a new ingestion job tied to a specific client contract and tenant."""
    record = _engine.create_job(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request=request,
    )
    return _to_response(record)


@router.post(
    "/{job_id}/upload",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload dataset and execute ingestion workflow.",
)
async def upload_job_file(
    job_id: str,
    file: Annotated[UploadFile, File(...)],
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_project_id: Annotated[str, Header(alias="X-Project-ID")],
) -> JobResponse:
    """Upload spreadsheet or ZIP archive to job and execute workflow activities."""
    job = _engine.get_job(x_tenant_id, x_project_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    # Resolve contract
    contract = _contracts.get(job.contract_id)
    if not contract:
        # Fallback to default contract matching tenant
        contract = ClientContract(
            contract_id=job.contract_id,
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            version="1.0.0",
            expected_assets=["COMP_1", "COMP_2", "COMP_3", "COMP_4"],
            required_signals=["PRESSURE", "TEMP"],
            allowed_units={"PRESSURE": ["bar", "psi"], "TEMP": ["C", "F"]},
            timezone="UTC",
            partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
        )

    raw_bytes = await file.read()
    filename = file.filename or "dataset.xlsx"

    updated_job = _engine.start_job(
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        job_id=job_id,
        raw_bytes=raw_bytes,
        filename=filename,
        contract=contract,
    )

    return _to_response(updated_job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Query job execution status and stage metadata.",
)
async def get_job_status(
    job_id: str,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_project_id: Annotated[str, Header(alias="X-Project-ID")],
) -> JobResponse:
    """Fetch current execution status for a job enforcing tenant isolation."""
    job = _engine.get_job(x_tenant_id, x_project_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return _to_response(job)


@router.get(
    "/{job_id}/reviews",
    response_model=list[ReviewItem],
    summary="List pending review items for a job awaiting steward approval.",
)
async def list_job_reviews(
    job_id: str,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_project_id: Annotated[str, Header(alias="X-Project-ID")],
) -> list[ReviewItem]:
    """Retrieve all pending review items associated with this job."""
    job = _engine.get_job(x_tenant_id, x_project_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    items: list[ReviewItem] = []
    for rid in job.review_item_ids:
        item = _engine.activities.review_queue.get(rid)
        if item:
            items.append(item)
    return items


@router.post(
    "/{job_id}/reviews/{review_id}/decision",
    response_model=JobResponse,
    summary="Submit steward approval/rejection decision, unblocking workflow wait-state.",
)
async def submit_review_decision(
    job_id: str,
    review_id: str,
    decision: ReviewDecisionRequest,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_project_id: Annotated[str, Header(alias="X-Project-ID")],
) -> JobResponse:
    """Record steward decision and unblock job workflow execution."""
    job = _engine.get_job(x_tenant_id, x_project_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    contract = _contracts.get(job.contract_id) or ClientContract(
        contract_id=job.contract_id,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        version="1.0.0",
        expected_assets=["COMP_1", "COMP_2", "COMP_3", "COMP_4"],
        required_signals=["PRESSURE", "TEMP"],
        allowed_units={"PRESSURE": ["bar", "psi"], "TEMP": ["C", "F"]},
        timezone="UTC",
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )

    try:
        updated_job = _engine.resume_with_review_decision(
            tenant_id=x_tenant_id,
            project_id=x_project_id,
            job_id=job_id,
            review_id=review_id,
            decision=decision,
            contract=contract,
        )
        return _to_response(updated_job)
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{job_id}/artifacts",
    response_model=dict[str, str],
    summary="List available published Parquet tables, reports, and handoff manifests.",
)
async def list_job_artifacts(
    job_id: str,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_project_id: Annotated[str, Header(alias="X-Project-ID")],
) -> dict[str, str]:
    """Return dictionary of artifact filenames to their relative download URIs."""
    job = _engine.get_job(x_tenant_id, x_project_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    if not job.dataset_id:
        return {}

    dataset_id = job.dataset_id
    base_prefix = f"{x_tenant_id}/{x_project_id}/published/{dataset_id}"

    artifacts: dict[str, str] = {
        "validation-report.json": f"{base_prefix}/validation-report.json",
        "handoff.json": f"{base_prefix}/handoff.json",
    }

    meas_key = f"{base_prefix}/tables/batch-measurements.parquet"
    if _storage.exists(meas_key):
        artifacts["batch-measurements.parquet"] = meas_key

    prov_key = f"{base_prefix}/provenance/batch-source-map.parquet"
    if _storage.exists(prov_key):
        artifacts["batch-source-map.parquet"] = prov_key

    return artifacts


@router.get(
    "/{job_id}/artifacts/{artifact_path:path}",
    summary="Download specific published Parquet table or JSON manifest.",
)
async def download_job_artifact(
    job_id: str,
    artifact_path: str,
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    x_project_id: Annotated[str, Header(alias="X-Project-ID")],
) -> Response:
    """Download artifact bytes ensuring tenant authorization."""
    job = _engine.get_job(x_tenant_id, x_project_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    # Sanitize and resolve target path
    if not _storage.exists(artifact_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_path}' not found.",
        )

    # Ensure path belongs to tenant
    if not artifact_path.startswith(f"{x_tenant_id}/{x_project_id}"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: cross-tenant access denied.",
        )

    data = _storage.get(artifact_path)
    is_json = artifact_path.endswith(".json")
    content_type = "application/json" if is_json else "application/octet-stream"

    return Response(content=data, media_type=content_type)
