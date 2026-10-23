"""Admission Gate orchestrating inspection, immutable raw storage, and manifest generation."""

import hashlib
import uuid
from datetime import UTC, datetime

from src.compiler.admission.config import AdmissionConfig
from src.compiler.admission.inspector import inspect_archive
from src.compiler.admission.models import AdmissionResult
from src.compiler.contracts.enums import JobResultState
from src.compiler.contracts.manifests import UploadManifest
from src.compiler.storage.object_store import ObjectStore


class AdmissionGate:
    """Security and admission gate for raw client uploads."""

    def __init__(
        self,
        storage: ObjectStore,
        config: AdmissionConfig | None = None,
    ) -> None:
        self.storage = storage
        self.config = config or AdmissionConfig()

    def admit(
        self,
        raw_bytes: bytes,
        filename: str,
        tenant_id: str,
        project_id: str,
    ) -> AdmissionResult:
        """Admit a raw client file into the compiler pipeline.

        Non-negotiable guarantees:
        1. Immutable storage: raw bytes are never mutated.
        2. Cryptographic digest: SHA-256 computed on original upload.
        3. Security verification: Rejects traversal, bombs, and corrupted archives.
        4. Rejected files never reach readers or execution stages.
        """
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        object_id = f"obj_{uuid.uuid4().hex}"

        # 1. Run low-level security and structural inspection
        inspection = inspect_archive(
            raw_bytes=raw_bytes,
            filename=filename,
            config=self.config,
        )

        if not inspection.is_valid:
            return AdmissionResult(
                object_id=object_id,
                sha256=sha256,
                status=JobResultState.FAILED,
                archive_type=inspection.archive_type,
                storage_uri=None,
                manifest=None,
                errors=inspection.errors,
                warnings=inspection.warnings,
            )

        # 2. Persist raw payload immutably to partitioned object store
        storage_key = f"raw/{tenant_id}/{project_id}/{object_id}.bin"
        storage_uri = self.storage.put(storage_key, raw_bytes)

        # 3. Construct the official UploadManifest
        manifest = UploadManifest(
            tenant_id=tenant_id,
            project_id=project_id,
            upload_id=object_id,
            archive_type=inspection.archive_type,
            uploaded_at=datetime.now(UTC),
            total_files=len(inspection.detected_entries),
            total_compressed_bytes=len(raw_bytes),
            files=inspection.detected_entries,
        )

        return AdmissionResult(
            object_id=object_id,
            sha256=sha256,
            status=JobResultState.ACCEPTED,
            archive_type=inspection.archive_type,
            storage_uri=storage_uri,
            manifest=manifest,
            errors=[],
            warnings=inspection.warnings,
        )
