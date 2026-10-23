"""Structural discovery engine orchestrating grid, regions, headers, and ambiguity gates."""

from __future__ import annotations

from typing import Protocol

from src.compiler.contracts.structure import (
    CellDetail,
    RegionBoundary,
    SheetStructure,
    WorkbookStructure,
)
from src.compiler.structure.ambiguity_scorer import AmbiguityScorer
from src.compiler.structure.header_reconstructor import HeaderReconstructor
from src.compiler.structure.occupancy_grid import OccupancyGrid
from src.compiler.structure.region_detector import RegionDetector
from src.compiler.structure.types import DiscoveredLayout, TableRegionLayout


class StructuralDiscoveryEngine(Protocol):
    """Protocol satisfied by structural discovery implementations."""

    def discover_sheet(
        self,
        sheet: SheetStructure,
        cells: list[CellDetail] | None = None,
    ) -> DiscoveredLayout:
        """Analyze a sheet's structural layout and return DiscoveredLayout."""
        ...

    def discover_workbook(
        self,
        workbook: WorkbookStructure,
    ) -> list[DiscoveredLayout]:
        """Analyze all worksheets in a workbook."""
        ...


class RuleBasedDiscoveryEngine:
    """Production rule-based discovery engine using occupancy grids and header reconstruction."""

    def __init__(self) -> None:
        self.scorer = AmbiguityScorer()

    def discover_sheet(
        self,
        sheet: SheetStructure,
        cells: list[CellDetail] | None = None,
    ) -> DiscoveredLayout:
        """Execute deterministic layout recognition for one worksheet."""
        effective_cells = cells if cells is not None else sheet.cells_sample

        grid = OccupancyGrid(
            max_row=sheet.max_row,
            max_col=sheet.max_col,
            cells=effective_cells,
            merged_ranges=sheet.merged_ranges,
        )

        detector = RegionDetector(grid)
        reconstructor = HeaderReconstructor(grid)

        boundaries, metadata_entries = detector.detect_regions()

        tables: list[TableRegionLayout] = []
        unassigned_regions: list[RegionBoundary] = []

        for b in boundaries:
            if b.region_type == "table":
                header_rows, data_start_row = detector.identify_header_band(b)
                columns = reconstructor.reconstruct_headers(
                    header_rows=header_rows,
                    min_col=b.min_col,
                    max_col=b.max_col,
                )
                tables.append(
                    TableRegionLayout(
                        boundary=b,
                        header_rows=header_rows,
                        data_start_row=data_start_row,
                        data_end_row=b.max_row,
                        columns=columns,
                    )
                )
            elif b.region_type == "metadata_block":
                # Metadata blocks are cataloged; do not treat as unassigned
                continue
            else:
                unassigned_regions.append(b)

        verdict, error_codes, diagnostics = self.scorer.evaluate_layout(
            tables=tables,
            unassigned_regions=unassigned_regions,
        )

        return DiscoveredLayout(
            sheet_name=sheet.name,
            tables=tables,
            metadata_entries=metadata_entries,
            unassigned_regions=unassigned_regions,
            verdict=verdict,
            error_codes=error_codes,
            diagnostic_messages=diagnostics,
        )

    def discover_workbook(
        self,
        workbook: WorkbookStructure,
    ) -> list[DiscoveredLayout]:
        """Execute structural discovery across all sheets in a workbook."""
        results: list[DiscoveredLayout] = []
        for sheet in workbook.sheets:
            results.append(self.discover_sheet(sheet))
        return results
