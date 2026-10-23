import hashlib
from pathlib import Path

from src.compiler.admission import AdmissionGate
from src.compiler.contracts.enums import ArchiveType, JobResultState
from src.compiler.storage.object_store import LocalFileSystemObjectStore


def test_admission_accepts_valid_single_xlsx(tmp_path: Path):
    """Verify that a genuine single XLSX workbook is admitted and stored immutably."""
    fixture_path = Path("tests/golden/fixtures/excel_simple/simple_table_ltds.xlsx")
    raw_bytes = fixture_path.read_bytes()
    expected_sha = hashlib.sha256(raw_bytes).hexdigest()

    storage = LocalFileSystemObjectStore(tmp_path)
    gate = AdmissionGate(storage)

    result = gate.admit(
        raw_bytes=raw_bytes,
        filename="simple_table_ltds.xlsx",
        tenant_id="tenant_alpha",
        project_id="proj_beta",
    )

    assert result.status == JobResultState.ACCEPTED
    assert result.archive_type == ArchiveType.SINGLE_XLSX
    assert result.sha256 == expected_sha
    assert result.storage_uri is not None
    assert len(result.errors) == 0

    # Verify storage immutability (read back from storage)
    stored_bytes = storage.get(f"raw/tenant_alpha/proj_beta/{result.object_id}.bin")
    assert stored_bytes == raw_bytes

    # Verify manifest
    assert result.manifest is not None
    assert result.manifest.total_files == 1
    assert result.manifest.total_compressed_bytes == len(raw_bytes)
    assert result.manifest.files[0].sha256 == expected_sha


def test_admission_accepts_valid_zip_batch(tmp_path: Path):
    """Verify that a valid multi-file ZIP archive is admitted and file entries cataloged."""
    fixture_path = Path("tests/golden/fixtures/zip_mixed/batch_5_compressors.zip")
    raw_bytes = fixture_path.read_bytes()

    storage = LocalFileSystemObjectStore(tmp_path)
    gate = AdmissionGate(storage)

    result = gate.admit(
        raw_bytes=raw_bytes,
        filename="batch_5_compressors.zip",
        tenant_id="tenant_alpha",
        project_id="proj_beta",
    )

    assert result.status == JobResultState.ACCEPTED
    assert result.archive_type == ArchiveType.ZIP_ARCHIVE
    assert result.manifest is not None
    assert result.manifest.total_files == 5
    assert len(result.manifest.files) == 5

    # Check file entry metadata
    entry_names = {f.relative_path for f in result.manifest.files}
    assert "compressor_log_1.xlsx" in entry_names
    assert "compressor_log_defective.xlsx" in entry_names
