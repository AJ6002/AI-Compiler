"""Structural representation contracts capturing raw workbook layout."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import DateEpoch


class RegionBoundary(BaseModel):
    """Bounding box for a table or metadata block within a worksheet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_row: int = Field(..., ge=1)
    max_row: int = Field(..., ge=1)
    min_col: int = Field(..., ge=1)
    max_col: int = Field(..., ge=1)
    region_type: str = Field(default="table", description="table, metadata_block, or header_band")


class CellDetail(BaseModel):
    """Detailed structural capture of a single cell."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coordinate: str = Field(..., description="A1 notation coordinate.")
    row: int = Field(..., ge=1)
    column: int = Field(..., ge=1)
    data_type: str = Field(..., description="s=string, n=numeric, d=datetime, f=formula, etc.")
    raw_value: Any = Field(default=None, description="Raw unparsed cell value.")
    formula: str | None = Field(default=None, description="Formula expression if present.")
    cached_value: Any = Field(default=None, description="Cached formula evaluation if present.")
    number_format: str | None = Field(default=None, description="Excel number format string.")
    is_merged: bool = Field(
        default=False, description="Whether this cell belongs to a merged range."
    )


class SheetStructure(BaseModel):
    """Structural layout and metrics for one worksheet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., description="Worksheet tab name.")
    index: int = Field(..., ge=0, description="0-indexed position in workbook.")
    max_row: int = Field(..., ge=0)
    max_col: int = Field(..., ge=0)
    merged_ranges: list[str] = Field(
        default_factory=list, description="Merged ranges (e.g. A1:D1)."
    )
    candidate_regions: list[RegionBoundary] = Field(default_factory=list)
    cells_sample: list[CellDetail] = Field(
        default_factory=list,
        description="Bounded sample of cell details for inspection.",
    )


class WorkbookStructure(BaseContract):
    """Native structural capture of an entire spreadsheet workbook."""

    source_sha256: str = Field(..., description="SHA-256 digest of the raw source file.")
    workbook_name: str = Field(..., description="Original filename.")
    date_epoch: DateEpoch = Field(default=DateEpoch.EPOCH_1900, description="Base date epoch.")
    sheets: list[SheetStructure] = Field(..., min_length=1, description="Contained worksheets.")
