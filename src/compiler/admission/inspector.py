"""Low-level archive inspector providing cryptographic, path safety, and expansion checks."""

import hashlib
import io
import os
import zipfile
from pathlib import PurePosixPath

from src.compiler.admission.config import AdmissionConfig
from src.compiler.admission.models import InspectionOutcome
from src.compiler.contracts.enums import ArchiveType, ErrorCode, ErrorSeverity
from src.compiler.contracts.manifests import FileEntry
from src.compiler.contracts.validation import ValidationErrorItem

# Magic bytes signature for standard PKZIP archives
ZIP_MAGIC_BYTES = b"PK\x03\x04"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ZIP_MIME = "application/zip"


def is_path_traversal(entry_name: str) -> bool:
    """Check if an archive entry path attempts traversal or absolute referencing."""
    # Check for drive letters (e.g. C: or c:)
    if len(entry_name) >= 2 and entry_name[1] == ":":
        return True

    # Check for leading backslashes or slashes
    if entry_name.startswith(("/", "\\")):
        return True

    # Normalize posix path and check components for traversal
    normalized = PurePosixPath(entry_name)
    parts = normalized.parts
    if ".." in parts:
        return True

    if normalized.is_absolute():
        return True

    return False


def inspect_archive(
    raw_bytes: bytes,
    filename: str,
    config: AdmissionConfig | None = None,
) -> InspectionOutcome:
    """Inspect raw upload bytes against admission security rules."""
    config = config or AdmissionConfig()
    errors: list[ValidationErrorItem] = []
    warnings: list[ValidationErrorItem] = []

    # 1. Total payload size check
    if len(raw_bytes) > config.max_compressed_bytes:
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_ADM_MAX_SIZE_EXCEEDED,
                severity=ErrorSeverity.FATAL,
                message=(
                    f"Upload size {len(raw_bytes)} bytes exceeds maximum allowed "
                    f"{config.max_compressed_bytes} bytes"
                ),
                remediation="Compress payload or split into smaller batches.",
            )
        )
        return InspectionOutcome(
            is_valid=False,
            archive_type=ArchiveType.SINGLE_XLSX,
            errors=errors,
        )

    # 2. Magic byte verification
    if not raw_bytes.startswith(ZIP_MAGIC_BYTES):
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_ADM_FILE_CORRUPT,
                severity=ErrorSeverity.FATAL,
                message="File signature mismatch: expected valid PKZIP header (PK\\x03\\x04).",
                remediation="Ensure the file is a genuine .xlsx workbook or .zip archive.",
            )
        )
        return InspectionOutcome(
            is_valid=False,
            archive_type=ArchiveType.SINGLE_XLSX,
            errors=errors,
        )

    # 3. Open archive safely in memory
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_ADM_FILE_CORRUPT,
                severity=ErrorSeverity.FATAL,
                message=f"Archive structure corrupt: {exc}",
                remediation="Re-export or re-create the archive.",
            )
        )
        return InspectionOutcome(
            is_valid=False,
            archive_type=ArchiveType.SINGLE_XLSX,
            errors=errors,
        )

    # 4. Determine whether archive is a single XLSX or a ZIP bundle
    namelist = zf.namelist()
    is_xlsx = "[Content_Types].xml" in namelist or "xl/workbook.xml" in namelist
    archive_type = ArchiveType.SINGLE_XLSX if is_xlsx else ArchiveType.ZIP_ARCHIVE

    # 5. Check file entry counts
    if not is_xlsx and len(namelist) > config.max_file_count:
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_ADM_MAX_SIZE_EXCEEDED,
                severity=ErrorSeverity.FATAL,
                message=(
                    f"Archive contains {len(namelist)} entries, exceeding limit "
                    f"of {config.max_file_count}."
                ),
                remediation="Split archive into smaller multi-file batches.",
            )
        )

    # 6. Detailed per-entry inspection
    total_uncompressed = 0
    file_entries: list[FileEntry] = []

    for info in zf.infolist():
        # Skip directory entries
        if info.is_dir() or info.filename.endswith(("/", "\\")):
            continue

        # Check path traversal
        if is_path_traversal(info.filename):
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_ADM_PATH_TRAVERSAL,
                    severity=ErrorSeverity.FATAL,
                    message=f"Illegal path traversal detected in entry: '{info.filename}'",
                    remediation="Remove relative (..) or absolute path references from entries.",
                )
            )

        # Check encryption / password protection
        if info.flag_bits & 0x1 != 0:
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_ADM_UNSUPPORTED_FORMAT,
                    severity=ErrorSeverity.FATAL,
                    message=(
                        f"Encrypted entry detected: '{info.filename}'. Encrypted files unsupported."
                    ),
                    remediation="Decrypt or remove password protection prior to admission.",
                )
            )

        # Check nested archives
        _, ext = os.path.splitext(info.filename.lower())
        if not is_xlsx and ext == ".zip" and config.max_nesting_depth <= 1:
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_ADM_UNSUPPORTED_FORMAT,
                    severity=ErrorSeverity.FATAL,
                    message=f"Nested zip archive detected: '{info.filename}'. Nested unsupported.",
                    remediation="Unpack nested archives into a single flat archive.",
                )
            )

        # Check single entry size limit
        if info.file_size > config.max_single_entry_bytes:
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_ADM_ZIP_BOMB,
                    severity=ErrorSeverity.FATAL,
                    message=(
                        f"Entry '{info.filename}' expanded size ({info.file_size} bytes) exceeds "
                        f"limit of {config.max_single_entry_bytes} bytes."
                    ),
                    remediation="Reduce individual file size.",
                )
            )

        # Check entry compression ratio
        compressed_size = max(info.compress_size, 1)
        ratio = info.file_size / compressed_size
        if ratio > config.max_expansion_ratio and info.file_size > 1024 * 1024:
            errors.append(
                ValidationErrorItem(
                    code=ErrorCode.ERR_ADM_ZIP_BOMB,
                    severity=ErrorSeverity.FATAL,
                    message=(
                        f"Suspicious compression ratio ({ratio:.1f}:1) for entry '{info.filename}'."
                    ),
                    remediation="Ensure file contains genuine operational data.",
                )
            )

        total_uncompressed += info.file_size

        # Extract entry bytes to compute per-file SHA-256 if no fatal errors so far
        if not errors:
            entry_bytes = zf.read(info)
            entry_sha = hashlib.sha256(entry_bytes).hexdigest()
            entry_mime = XLSX_MIME if ext in (".xlsx", ".xlsm") else "application/octet-stream"
            file_entries.append(
                FileEntry(
                    relative_path=info.filename,
                    sha256=entry_sha,
                    byte_size=info.file_size,
                    mime_type_detected=entry_mime,
                )
            )

    # 7. Check cumulative uncompressed expansion limit
    if total_uncompressed > config.max_expanded_bytes:
        errors.append(
            ValidationErrorItem(
                code=ErrorCode.ERR_ADM_ZIP_BOMB,
                severity=ErrorSeverity.FATAL,
                message=(
                    f"Cumulative uncompressed size {total_uncompressed} bytes exceeds "
                    f"maximum limit of {config.max_expanded_bytes} bytes."
                ),
                remediation="Upload smaller batches of workbooks.",
            )
        )

    # If single XLSX, create single entry representing the workbook itself
    if is_xlsx and not errors:
        file_entries = [
            FileEntry(
                relative_path=os.path.basename(filename) or "workbook.xlsx",
                sha256=hashlib.sha256(raw_bytes).hexdigest(),
                byte_size=len(raw_bytes),
                mime_type_detected=XLSX_MIME,
            )
        ]

    is_valid = len(errors) == 0

    return InspectionOutcome(
        is_valid=is_valid,
        archive_type=archive_type,
        detected_entries=file_entries,
        total_uncompressed_bytes=total_uncompressed,
        errors=errors,
        warnings=warnings,
    )
