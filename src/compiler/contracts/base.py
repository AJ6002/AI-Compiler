"""Base contract definition enforcing immutability, extra-field rejection, and versioning."""

from pydantic import BaseModel, ConfigDict, Field


class BaseContract(BaseModel):
    """Abstract base model for all AICONNEX versioned contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    schema_version: str = Field(
        default="1.0.0",
        description="Semantic version of the contract schema.",
    )
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Authorized tenant identity scoping this contract.",
    )
    project_id: str = Field(
        ...,
        min_length=1,
        description="Project identifier within the tenant scope.",
    )
