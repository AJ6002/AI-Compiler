import io
import zipfile
from pathlib import Path

from src.compiler.admission import AdmissionConfig, AdmissionGate
from src.compiler.contracts.enums import ErrorCode, JobResultState
from src.compiler.storage.object_store import LocalFileSystemObjectStore


def test_admission_rejects_corrupted_signature(tmp_path: Path):
    """Verify that non-zip/non-xlsx payloads are rejected with ERR_ADM_FILE_CORRUPT."""
    corrupt_fixture = Path("tests/golden/fixtures/failure_cases/corrupted_signature.xlsx")
    raw_bytes = corrupt_fixture.read_bytes()

    gate = AdmissionGate(LocalFileSystemObjectStore(tmp_path))
    result = gate.admit(
        raw_bytes=raw_bytes,
        filename="corrupted_signature.xlsx",
        tenant_id="tenant_sec",
        project_id="proj_sec",
    )

    assert result.status == JobResultState.FAILED
    assert result.manifest is None
    assert any(e.code == ErrorCode.ERR_ADM_FILE_CORRUPT for e in result.errors)


def test_admission_rejects_path_traversal(tmp_path: Path):
    """Verify that entries containing relative path traversal (..) are rejected."""
    traversal_fixture = Path("tests/golden/fixtures/failure_cases/traversal_attack.zip")
    raw_bytes = traversal_fixture.read_bytes()

    gate = AdmissionGate(LocalFileSystemObjectStore(tmp_path))
    result = gate.admit(
        raw_bytes=raw_bytes,
        filename="traversal_attack.zip",
        tenant_id="tenant_sec",
        project_id="proj_sec",
    )

    assert result.status == JobResultState.FAILED
    assert result.manifest is None
    assert any(e.code == ErrorCode.ERR_ADM_PATH_TRAVERSAL for e in result.errors)


def test_admission_rejects_zip_bomb_expansion_ratio(tmp_path: Path):
    """Verify that archives with suspicious expansion ratios (> 100:1) are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Repetitive zeroes compress from 5MB to a few KB (ratio > 500:1)
        zf.writestr("zeroes.bin", b"\x00" * (5 * 1024 * 1024))

    raw_bytes = buf.getvalue()
    config = AdmissionConfig(max_expansion_ratio=50.0)
    gate = AdmissionGate(LocalFileSystemObjectStore(tmp_path), config=config)

    result = gate.admit(
        raw_bytes=raw_bytes,
        filename="bomb.zip",
        tenant_id="tenant_sec",
        project_id="proj_sec",
    )

    assert result.status == JobResultState.FAILED
    assert any(e.code == ErrorCode.ERR_ADM_ZIP_BOMB for e in result.errors)


def test_admission_rejects_cumulative_size_limit(tmp_path: Path):
    """Verify that cumulative uncompressed size exceeding max_expanded_bytes is rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for idx in range(5):
            zf.writestr(f"file_{idx}.bin", b"X" * (1024 * 1024))  # 5 MB total

    raw_bytes = buf.getvalue()
    config = AdmissionConfig(max_expanded_bytes=3 * 1024 * 1024)  # 3 MB limit
    gate = AdmissionGate(LocalFileSystemObjectStore(tmp_path), config=config)

    result = gate.admit(
        raw_bytes=raw_bytes,
        filename="large.zip",
        tenant_id="tenant_sec",
        project_id="proj_sec",
    )

    assert result.status == JobResultState.FAILED
    assert any(e.code == ErrorCode.ERR_ADM_ZIP_BOMB for e in result.errors)


def test_admission_rejects_excessive_file_count(tmp_path: Path):
    """Verify that archives exceeding max_file_count are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for idx in range(15):
            zf.writestr(f"file_{idx}.txt", b"ok")

    raw_bytes = buf.getvalue()
    config = AdmissionConfig(max_file_count=10)
    gate = AdmissionGate(LocalFileSystemObjectStore(tmp_path), config=config)

    result = gate.admit(
        raw_bytes=raw_bytes,
        filename="too_many_files.zip",
        tenant_id="tenant_sec",
        project_id="proj_sec",
    )

    assert result.status == JobResultState.FAILED
    assert any(e.code == ErrorCode.ERR_ADM_MAX_SIZE_EXCEEDED for e in result.errors)
