from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


@pytest.mark.asyncio
async def test_api_upload_success():
    """Verify that a valid XLSX file upload succeeds with 201 Created."""
    fixture_path = Path("tests/golden/fixtures/excel_simple/simple_table_ltds.xlsx")
    file_bytes = fixture_path.read_bytes()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/uploads",
            headers={
                "X-Tenant-ID": "tenant_123",
                "X-Project-ID": "project_456",
            },
            files={"file": ("simple_table_ltds.xlsx", file_bytes, "application/octet-stream")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["archive_type"] == "single_xlsx"
    assert data["manifest"]["total_files"] == 1


@pytest.mark.asyncio
async def test_api_upload_missing_headers():
    """Verify that requests missing tenant/project authentication headers are rejected with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/uploads",
            files={"file": ("test.xlsx", b"dummy", "application/octet-stream")},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_upload_rejects_malicious_archive():
    """Verify that uploading a malicious zip fails admission with 400 Bad Request."""
    traversal_fixture = Path("tests/golden/fixtures/failure_cases/traversal_attack.zip")
    file_bytes = traversal_fixture.read_bytes()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/uploads",
            headers={
                "X-Tenant-ID": "tenant_123",
                "X-Project-ID": "project_456",
            },
            files={"file": ("traversal_attack.zip", file_bytes, "application/zip")},
        )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["status"] == "FAILED"
    error_codes = [e["code"] for e in data["detail"]["errors"]]
    assert "ERR_ADM_PATH_TRAVERSAL" in error_codes
