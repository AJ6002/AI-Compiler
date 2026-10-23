"""API endpoints for secure client file upload and admission."""

from typing import Annotated

from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status

from apps.api.config import settings
from src.compiler.admission.gate import AdmissionGate
from src.compiler.admission.models import AdmissionResult
from src.compiler.contracts.enums import JobResultState
from src.compiler.storage.object_store import LocalFileSystemObjectStore

router = APIRouter(prefix="/uploads", tags=["Uploads"])

# Initialize default storage backend and admission gate
_storage = LocalFileSystemObjectStore(settings.local_storage_root)
_gate = AdmissionGate(_storage)


@router.post(
    "",
    response_model=AdmissionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an authorized Excel or ZIP dataset for admission.",
)
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    x_tenant_id: Annotated[
        str,
        Header(alias="X-Tenant-ID", description="Authorized tenant identifier"),
    ],
    x_project_id: Annotated[
        str,
        Header(alias="X-Project-ID", description="Project identifier within tenant"),
    ],
) -> AdmissionResult:
    """Accept and admit raw client spreadsheet or ZIP archive into immutable storage."""
    raw_bytes = await file.read()
    filename = file.filename or "upload.bin"

    result = _gate.admit(
        raw_bytes=raw_bytes,
        filename=filename,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
    )

    if result.status == JobResultState.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.model_dump(),
        )

    return result
