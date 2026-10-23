"""Structural ambiguity evaluation and REVIEW_REQUIRED routing."""

from __future__ import annotations

from collections import Counter

from src.compiler.contracts.enums import ErrorCode, JobResultState
from src.compiler.contracts.structure import RegionBoundary
from src.compiler.structure.types import TableRegionLayout


class AmbiguityScorer:
    """Evaluates structural certainty and routes ambiguous layouts to REVIEW_REQUIRED."""

    def evaluate_layout(
        self,
        tables: list[TableRegionLayout],
        unassigned_regions: list[RegionBoundary],
    ) -> tuple[JobResultState, list[ErrorCode], list[str]]:
        """Assess table regions, duplicate paths, and dispersed segments.

        Returns (verdict, error_codes, diagnostic_messages).
        """
        error_codes: list[ErrorCode] = []
        diagnostics: list[str] = []

        if not tables:
            # Empty sheet or no tables found
            diagnostics.append("No viable data tables identified in worksheet.")
            return (
                JobResultState.REVIEW_REQUIRED,
                [ErrorCode.ERR_STRUCT_DISPERSED_REGIONS],
                diagnostics,
            )

        # Check for unassigned or fragmented regions
        if unassigned_regions:
            error_codes.append(ErrorCode.ERR_STRUCT_DISPERSED_REGIONS)
            count = len(unassigned_regions)
            diagnostics.append(
                f"Discovered {count} unassigned or dispersed regions outside primary tables."
            )

        # Check each table for header ambiguities and duplicate column paths
        for idx, table in enumerate(tables):
            # Check duplicate reconstructed column paths
            paths = [col.path for col in table.columns]
            counts = Counter(paths)
            duplicates = [p for p, count in counts.items() if count > 1]

            if duplicates:
                error_codes.append(ErrorCode.ERR_STRUCT_DUPLICATE_COLUMNS)
                diagnostics.append(
                    f"Table {idx + 1} has duplicate unresolved column headers: {duplicates}"
                )

            # Check for empty data region (header exists but no data rows)
            if table.data_start_row > table.data_end_row:
                error_codes.append(ErrorCode.ERR_STRUCT_AMBIGUOUS_HEADER)
                diagnostics.append(f"Table {idx + 1} contains header rows but zero data rows.")

            # Check for single-column or degenerate tables
            if len(table.columns) == 0:
                error_codes.append(ErrorCode.ERR_STRUCT_AMBIGUOUS_HEADER)
                diagnostics.append(f"Table {idx + 1} has no valid columns.")

        if error_codes:
            return JobResultState.REVIEW_REQUIRED, list(set(error_codes)), diagnostics

        return JobResultState.ACCEPTED, [], diagnostics
