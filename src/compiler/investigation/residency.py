"""Model residency and client data sovereignty policies.

Per build plan Phase 8:
Entry gate: per client, a recorded and approved model-residency decision must exist
before any model call is made. If unresolved or prohibited, route only to a self-hosted
model or human steward review.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ModelResidency(StrEnum):
    """Client model residency and data sovereignty classification."""

    PROHIBITED = "prohibited"  # Strict sovereignty: zero external or model calls permitted
    SELF_HOSTED = "self_hosted"  # Model runs strictly within client VPC / on-premises
    CLOUD_AUTHORIZED = "cloud_authorized"  # Client authorized approved cloud model provider


class ResidencyPolicy(BaseModel):
    """Client-specific residency contract specifying allowed model execution tiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(..., description="Authorized tenant identifier.")
    project_id: str = Field(..., description="Project identifier.")
    residency: ModelResidency = Field(
        default=ModelResidency.PROHIBITED,
        description="Active model residency tier.",
    )
    allowed_providers: list[str] = Field(
        default_factory=list,
        description="Allowlisted model providers if CLOUD_AUTHORIZED.",
    )


def check_model_residency_permission(policy: ResidencyPolicy | None) -> tuple[bool, str]:
    """Check whether a model investigation call is authorized under client policy.

    Returns (is_permitted, diagnostic_message).
    """
    if policy is None:
        return False, "Model residency policy is unconfigured; default is PROHIBITED."

    if policy.residency == ModelResidency.PROHIBITED:
        return (
            False,
            f"Model residency is PROHIBITED for tenant '{policy.tenant_id}'. "
            "Routing directly to human data steward review.",
        )

    if policy.residency in (ModelResidency.SELF_HOSTED, ModelResidency.CLOUD_AUTHORIZED):
        return True, f"Model investigation authorized under {policy.residency.value}."

    return False, f"Unknown residency tier '{policy.residency}'."
