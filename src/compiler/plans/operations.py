"""Strongly typed parameter schemas and validators for allowlisted plan operations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.enums import PlanOperationType


class SelectRegionParams(BaseModel):
    """Parameters for selecting a bounded rectangular region."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_row: int = Field(..., ge=1, description="1-indexed starting row.")
    max_row: int = Field(..., ge=1, description="1-indexed ending row.")
    min_col: int = Field(..., ge=1, description="1-indexed starting column.")
    max_col: int = Field(..., ge=1, description="1-indexed ending column.")


class FlattenHeadersParams(BaseModel):
    """Parameters for flattening multi-row hierarchical header bands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    header_rows: list[int] = Field(..., min_length=1, description="1-indexed header rows.")
    separator: str = Field(default=".", description="Delimiter joining ancestor labels.")


class TypeCastParams(BaseModel):
    """Parameters for deterministic columnar type conversion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    casts: dict[str, str] = Field(
        ...,
        description="Mapping of column_name -> target_type (float, int, string, iso_datetime).",
    )


class ParseDurationParams(BaseModel):
    """Parameters for converting duration serials or elapsed string formats."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    columns: list[str] = Field(..., min_length=1, description="Column names containing durations.")


class FormulaPolicyParams(BaseModel):
    """Parameters governing formula cell handling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: Literal["use_cached_or_fail", "require_literal_only"] = Field(
        default="use_cached_or_fail",
        description="Policy for evaluating formula cell cached values.",
    )


class FilterRowsParams(BaseModel):
    """Parameters for filtering rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    drop_empty_rows: bool = Field(default=True, description="Drop rows where all cells are empty.")
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns in first column that indicate non-data footers.",
    )


class UnpivotParams(BaseModel):
    """Parameters for reshaping wide measurement rows into long telemetry observations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id_vars: list[str] = Field(
        ...,
        min_length=1,
        description="Columns preserved as dimension identifiers (e.g. timestamp, asset).",
    )
    value_vars: list[str] = Field(
        ...,
        min_length=1,
        description="Columns to unpivot into (signal_id, value) observation pairs.",
    )
    var_name: str = Field(default="signal_id", description="Target signal identifier column.")
    value_name: str = Field(default="value", description="Target measurement value column.")


OPERATION_PARAM_MODELS: dict[PlanOperationType, type[BaseModel]] = {
    PlanOperationType.SELECT_REGION: SelectRegionParams,
    PlanOperationType.FLATTEN_HEADERS: FlattenHeadersParams,
    PlanOperationType.TYPE_CAST: TypeCastParams,
    PlanOperationType.PARSE_DURATION: ParseDurationParams,
    PlanOperationType.FORMULA_POLICY: FormulaPolicyParams,
    PlanOperationType.FILTER_ROWS: FilterRowsParams,
    PlanOperationType.UNPIVOT: UnpivotParams,
}


def validate_operation_params(op: PlanOperationType, params: dict[str, Any]) -> BaseModel:
    """Validate raw parameter dictionary against the strongly typed operation model."""
    model_cls = OPERATION_PARAM_MODELS.get(op)
    if not model_cls:
        raise ValueError(f"Unknown or unsupported operation type: '{op}'")
    return model_cls.model_validate(params)
