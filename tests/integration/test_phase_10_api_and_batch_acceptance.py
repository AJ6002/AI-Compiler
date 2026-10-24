"""End-to-End Acceptance Tests for Phase 10: Control Plane API, Workflows, and AutoMLOps Handoff."""

import io
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers.jobs import register_contract
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import PartialBatchPolicy
from src.compiler.contracts.manifests import HandoffManifest
from src.compiler.workflows.models import JobStatus
from tests.mocks.automlops import MockAutoMLOpsConsumer

client = TestClient(app)


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "golden" / "fixtures"


def test_api_tenant_isolation():
    """Verify mismatched tenant header returns 404 and does not leak job state."""
    # 1. Create job under tenant_alpha
    resp = client.post(
        "/api/v1/jobs",
        json={"contract_id": "contract_compressor_fleet"},
        headers={"X-Tenant-ID": "tenant_alpha", "X-Project-ID": "proj_1"},
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]

    # 2. Query job with correct tenant succeeds
    auth_resp = client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"X-Tenant-ID": "tenant_alpha", "X-Project-ID": "proj_1"},
    )
    assert auth_resp.status_code == 200

    # 3. Query job with unauthorized tenant_beta returns 404
    unauth_resp = client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"X-Tenant-ID": "tenant_beta", "X-Project-ID": "proj_1"},
    )
    assert unauth_resp.status_code == 404


def test_phase_10_zip_batch_mixed_acceptance(fixtures_dir: Path):
    """Phase 10 Acceptance Test: 5-compressor zip batch with partial publication and review."""
    zip_path = fixtures_dir / "zip_mixed" / "batch_5_compressors.zip"
    assert zip_path.exists(), f"Golden fixture missing at {zip_path}"

    tenant_id = "tenant_oil_gas"
    project_id = "proj_station_4"

    # 1. Create Job via REST API
    create_resp = client.post(
        "/api/v1/jobs",
        json={"contract_id": "contract_compressor_fleet"},
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]
    assert create_resp.json()["status"] == JobStatus.PENDING

    # 2. Upload 5-compressor ZIP archive to trigger workflow
    zip_bytes = zip_path.read_bytes()
    upload_resp = client.post(
        f"/api/v1/jobs/{job_id}/upload",
        files={"file": ("batch_5_compressors.zip", zip_bytes, "application/zip")},
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert upload_resp.status_code == 202
    job_data = upload_resp.json()

    # 3. Verify workflow reached REVIEW_REQUIRED due to defective file
    assert job_data["status"] == JobStatus.REVIEW_REQUIRED
    assert len(job_data["review_item_ids"]) >= 1

    # 4. Check Artifacts Catalog: 4 valid compressors published under partial-batch policy
    artifacts_resp = client.get(
        f"/api/v1/jobs/{job_id}/artifacts",
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert artifacts_resp.status_code == 200
    catalog = artifacts_resp.json()
    assert "batch-measurements.parquet" in catalog
    assert "handoff.json" in catalog

    # 5. Download and inspect published measurements table
    meas_uri = catalog["batch-measurements.parquet"]
    table_resp = client.get(
        f"/api/v1/jobs/{job_id}/artifacts/{meas_uri}",
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert table_resp.status_code == 200
    meas_table = pq.read_table(io.BytesIO(table_resp.content))
    # 4 valid files * 40 rows = 160 measurement records
    assert meas_table.num_rows == 160
    assert set(meas_table.column("asset_id").to_pylist()) == {
        "COMP_1",
        "COMP_2",
        "COMP_3",
        "COMP_4",
    }

    # 6. Verify Downstream Mock AutoMLOps Consumer REJECTS bundle for automated training
    handoff_uri = catalog["handoff.json"]
    handoff_resp = client.get(
        f"/api/v1/jobs/{job_id}/artifacts/{handoff_uri}",
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert handoff_resp.status_code == 200
    handoff_data = json.loads(handoff_resp.content)
    handoff_manifest = HandoffManifest(**handoff_data)

    from apps.api.routers.jobs import _storage

    automlops_consumer = MockAutoMLOpsConsumer(store=_storage)
    pre_review_eval = automlops_consumer.consume(handoff_manifest)

    # Rejection assertion: cannot train on review-required dataset
    assert pre_review_eval.accepted_for_training is False
    assert "ERR_AUTOMLOPS_UNVERIFIED_DATASET" in pre_review_eval.rejection_reason

    # 7. Steward inspects review queue
    reviews_resp = client.get(
        f"/api/v1/jobs/{job_id}/reviews",
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert reviews_resp.status_code == 200
    review_items = reviews_resp.json()
    assert len(review_items) >= 1
    target_review_id = review_items[0]["review_id"]

    # 8. Steward resolves review with override approval
    decision_resp = client.post(
        f"/api/v1/jobs/{job_id}/reviews/{target_review_id}/decision",
        json={
            "approved": True,
            "reviewer": "lead_steward@aiconnex.com",
            "reason": "Approved partial batch; defective unit 5 quarantined for field maintenance.",
        },
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert decision_resp.status_code == 200


def test_real_world_dataset_tas_probe():
    """Verify ingestion of real-world compressor DPR archive (Dataset-TAS.zip) if present."""
    tas_path = Path(r"X:\TAS\dataset\data\raw\Dataset-TAS.zip")
    if not tas_path.exists():
        pytest.skip("Local test dataset Dataset-TAS.zip not available on current filesystem.")

    tenant_id = "tenant_tas"
    project_id = "proj_wadwan"

    # Register TAS Contract
    tas_contract = ClientContract(
        contract_id="contract_tas_dpr",
        tenant_id=tenant_id,
        project_id=project_id,
        version="1.0.0",
        expected_assets=["DPR Report"],
        required_signals=["Total Gas Inlet Per Day"],
        allowed_units={"Total Gas Inlet Per Day": ["SCM", "M3", "default"]},
        timezone="UTC",
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )
    register_contract(tas_contract)

    create_resp = client.post(
        "/api/v1/jobs",
        json={"contract_id": "contract_tas_dpr"},
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]

    upload_resp = client.post(
        f"/api/v1/jobs/{job_id}/upload",
        files={"file": ("Dataset-TAS.zip", tas_path.read_bytes(), "application/zip")},
        headers={"X-Tenant-ID": tenant_id, "X-Project-ID": project_id},
    )
    assert upload_resp.status_code == 202
    assert upload_resp.json()["status"] in (
        JobStatus.ACCEPTED,
        JobStatus.REVIEW_REQUIRED,
    )
