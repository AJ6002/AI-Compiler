"""Ground-truth oracle specifications and corpus catalog models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import ErrorCode, JobResultState, UnitSource


class CorpusCategory(StrEnum):
    """The 7 official test corpus categories defined in Phase 2 (G11)."""

    FLAT_CSV_GOLDEN = "flat_csv_golden"
    EXCEL_SIMPLE = "excel_simple"
    EXCEL_COMPLEX = "excel_complex"
    EXCEL_SCATTERED = "excel_scattered"
    EXCEL_FORMULA = "excel_formula"
    ZIP_MIXED = "zip_mixed"
    FAILURE_CASES = "failure_cases"


class OracleFixture(BaseModel):
    """Ground-truth oracle definition for an individual test workbook or archive."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: str = Field(..., description="Unique identifier for this test fixture.")
    category: CorpusCategory = Field(..., description="Corpus classification category.")
    relative_path: str = Field(..., description="Relative path within tests/golden/fixtures/.")
    sha256: str = Field(..., description="Expected SHA-256 hash of the input file.")
    is_synthetic: bool = Field(default=True, description="Always True for generated test fixtures.")
    expected_result_state: JobResultState = Field(..., description="Expected acceptance state.")
    expected_error_codes: list[ErrorCode] = Field(
        default_factory=list,
        description="Error codes expected to be flagged by validation gates.",
    )

    # Structural Expectations
    expected_sheet_names: list[str] = Field(default_factory=list)
    expected_row_count: int = Field(..., ge=0, description="Expected record count in main table.")
    expected_column_count: int = Field(..., ge=1, description="Expected column count.")

    # Signal and Unit Metadata (Gap G10)
    expected_signals: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of signal_id -> canonical_path.",
    )
    unit_sources: dict[str, UnitSource] = Field(
        default_factory=dict,
        description="Declared source location of units for each signal.",
    )

    # Temporal Bounds
    expected_time_range_utc: tuple[datetime, datetime] | None = Field(
        default=None,
        description="Expected (min_time, max_time) in UTC.",
    )
    expected_observation_count: int | None = Field(
        default=None,
        description="Expected count of unique (asset_id, timestamp_utc, raw_source_row) tuples.",
    )


class CorpusCatalog(BaseContract):
    """Master catalog indexing labeled test fixtures across all categories."""

    catalog_id: str = Field(..., description="Unique catalog version identifier.")
    fixtures: list[OracleFixture] = Field(
        ...,
        min_length=1,
        description="List of all registered test oracle fixtures.",
    )
