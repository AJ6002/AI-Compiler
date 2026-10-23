"""Unit tests for ModelResidency entry gate and client sovereignty."""

from src.compiler.investigation.residency import (
    ModelResidency,
    ResidencyPolicy,
    check_model_residency_permission,
)


def test_residency_unconfigured_defaults_to_prohibited() -> None:
    permitted, reason = check_model_residency_permission(None)
    assert not permitted
    assert "PROHIBITED" in reason


def test_residency_prohibited_blocks_invocation() -> None:
    policy = ResidencyPolicy(
        tenant_id="tenant-oil-gas",
        project_id="proj-strict",
        residency=ModelResidency.PROHIBITED,
    )
    permitted, reason = check_model_residency_permission(policy)
    assert not permitted
    assert "PROHIBITED" in reason
    assert "human data steward review" in reason


def test_residency_authorized_tiers_allow_invocation() -> None:
    cloud_policy = ResidencyPolicy(
        tenant_id="tenant-cloud",
        project_id="proj-cloud",
        residency=ModelResidency.CLOUD_AUTHORIZED,
        allowed_providers=["anthropic", "openai"],
    )
    permitted_cloud, _ = check_model_residency_permission(cloud_policy)
    assert permitted_cloud

    self_hosted_policy = ResidencyPolicy(
        tenant_id="tenant-onprem",
        project_id="proj-onprem",
        residency=ModelResidency.SELF_HOSTED,
    )
    permitted_sh, _ = check_model_residency_permission(self_hosted_policy)
    assert permitted_sh
