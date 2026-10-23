"""Base reader protocol and probe result schema for spreadsheet extraction."""

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.structure import CellDetail, WorkbookStructure


class ProbeResult(BaseModel):
    """Fast preliminary inspection of a spreadsheet workbook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sheet_names: list[str] = Field(..., description="List of worksheet names in tab order.")
    sheet_count: int = Field(..., ge=1, description="Total number of sheets.")
    date_epoch: str = Field(..., description="Detected date epoch: '1900' or '1904'.")
    is_macro_enabled: bool = Field(
        default=False, description="True if workbook contains VBA macros."
    )
    dimensions_map: dict[str, tuple[int, int]] = Field(
        default_factory=dict,
        description="Mapping of sheet_name -> (max_row, max_col).",
    )


class ExcelReader(Protocol):
    """Protocol satisfied by openpyxl baseline and any future challenger adapters."""

    def probe(self, source: bytes | Path) -> ProbeResult:
        """Inspect top-level workbook metadata without parsing cell contents."""
        ...

    def inspect(
        self,
        source: bytes | Path,
        tenant_id: str,
        project_id: str,
        max_preview_rows: int = 50,
        workbook_name: str | None = None,
    ) -> WorkbookStructure:
        """Extract native layout representation including merged cells and preview rows."""
        ...

    def extract_sheet_cells(
        self,
        source: bytes | Path,
        sheet_name: str,
        batch_size: int = 1000,
    ) -> Iterator[list[CellDetail]]:
        """Yield bounded batches of typed cell coordinates for downstream execution."""
        ...
