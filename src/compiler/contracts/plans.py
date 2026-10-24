"""Parse Plan contract specifying allowlisted, deterministic operations."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import PlanOperationType


class PlanOperation(BaseModel):
    """A single deterministic operation in a parse plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    op: PlanOperationType = Field(..., description="Allowlisted operation type.")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters specific to the operation.",
    )


class ParsePlan(BaseContract):
    """Declarative, deterministic instructions for extracting and reshaping a worksheet."""

    plan_id: str = Field(..., description="Unique plan identifier.")
    target_sheet: str = Field(..., description="Target worksheet name to apply this plan.")
    operations: list[PlanOperation] = Field(
        ...,
        min_length=1,
        description="Ordered sequence of allowlisted transformation operations.",
    )
    created_by: str | None = Field(
        default=None,
        description="Origin of plan: 'discovery', 'recipe:<id>', 'agent:<id>', or 'human:<id>'.",
    )
