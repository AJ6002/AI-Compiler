"""Recipe contract binding verified parse plans to structural signatures."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import SharingTier
from src.compiler.contracts.plans import ParsePlan


class StructuralSignature(BaseModel):
    """Structural features used to recognize recurring layout patterns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sheet_names: list[str] = Field(..., description="Expected worksheet names.")
    header_patterns: list[str] = Field(..., description="Ordered column header strings.")
    merge_fingerprint: list[str] = Field(
        default_factory=list,
        description="List of merged coordinate ranges.",
    )
    min_columns: int = Field(default=1, ge=1)


class Recipe(BaseContract):
    """Reviewed, versioned parsing plan with applicability checks."""

    recipe_id: str = Field(..., description="Unique recipe identifier.")
    version: str = Field(..., description="Semantic version string for this recipe.")
    generation_system: str = Field(
        ...,
        description="Identified client-side generation system producing this file.",
    )
    sharing_tier: SharingTier = Field(
        default=SharingTier.TENANT_BOUND,
        description="Whether this recipe is tenant-bound or an approved cross-client template.",
    )
    signature: StructuralSignature = Field(
        ...,
        description="Signature required for candidate matching.",
    )
    plan: ParsePlan = Field(..., description="The approved parse plan.")
    approved_by: str = Field(..., description="Identity of the approving engineer or steward.")
    approved_at: datetime = Field(..., description="Approval timestamp.")
    is_revoked: bool = Field(default=False, description="Whether this recipe has been revoked.")
