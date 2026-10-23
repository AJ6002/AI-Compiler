"""Region segmentation and metadata isolation for spreadsheet worksheets."""

from __future__ import annotations

from src.compiler.contracts.structure import RegionBoundary
from src.compiler.structure.occupancy_grid import OccupancyGrid
from src.compiler.structure.types import CellTypeSignature, MetadataEntry


class RegionDetector:
    """Discovers metadata blocks and table bounding boxes using occupancy and type transitions."""

    def __init__(self, grid: OccupancyGrid) -> None:
        self.grid = grid

    def detect_regions(
        self,
    ) -> tuple[list[RegionBoundary], list[MetadataEntry]]:
        """Identify candidate table boundaries and isolate key-value metadata blocks.

        Returns (candidate_regions, metadata_entries).
        """
        if self.grid.max_row == 0 or self.grid.max_col == 0:
            return [], []

        # Find all non-empty row indices
        non_empty_rows = [
            r for r in range(1, self.grid.max_row + 1) if self.grid.row_non_empty_count(r) > 0
        ]

        if not non_empty_rows:
            return [], []

        # Segment rows into continuous chunks separated by blank rows
        row_chunks: list[list[int]] = []
        current_chunk: list[int] = []

        for r in non_empty_rows:
            if not current_chunk or r == current_chunk[-1] + 1:
                current_chunk.append(r)
            else:
                row_chunks.append(current_chunk)
                current_chunk = [r]
        if current_chunk:
            row_chunks.append(current_chunk)

        boundaries: list[RegionBoundary] = []
        metadata_entries: list[MetadataEntry] = []

        for chunk_idx, chunk in enumerate(row_chunks):
            min_r = chunk[0]
            max_r = chunk[-1]

            # If this table chunk reaches the end of sampled preview rows,
            # extend to full sheet max_row
            if chunk_idx == len(row_chunks) - 1 and self.grid.max_row > max_r:
                max_r = self.grid.max_row

            # Determine column extent for this chunk
            active_cols: set[int] = set()
            for r in chunk:
                for c in range(1, self.grid.max_col + 1):
                    if self.grid.get_signature(r, c) != CellTypeSignature.EMPTY:
                        active_cols.add(c)

            if not active_cols:
                continue

            min_c = min(active_cols)
            max_c = max(active_cols)
            col_width = max_c - min_c + 1

            # Check if this chunk is a metadata block:
            # Typically narrow (<= 2 active columns or <= 3 columns total) and low row count
            # or distinct key-value colon patterns
            is_metadata_block = self._is_metadata_chunk(chunk, min_c, max_c, col_width)

            if is_metadata_block and len(row_chunks) > 1:
                boundaries.append(
                    RegionBoundary(
                        min_row=min_r,
                        max_row=max_r,
                        min_col=min_c,
                        max_col=max_c,
                        region_type="metadata_block",
                    )
                )
                # Extract metadata key-values
                for r in chunk:
                    entry = self._extract_metadata_row(r, min_c, max_c)
                    if entry is not None:
                        metadata_entries.append(entry)
            else:
                # Treat as a data table region
                boundaries.append(
                    RegionBoundary(
                        min_row=min_r,
                        max_row=max_r,
                        min_col=min_c,
                        max_col=max_c,
                        region_type="table",
                    )
                )

        return boundaries, metadata_entries

    def _is_metadata_chunk(
        self,
        chunk: list[int],
        min_c: int,
        max_c: int,
        col_width: int,
    ) -> bool:
        """Evaluate heuristics to determine if a row chunk represents metadata."""
        if len(chunk) > 10:
            return False

        # Narrow column span (<= 3 columns)
        if col_width <= 3:
            # Check for colon indicators or string label patterns in first column
            colon_found = False
            for r in chunk:
                val = self.grid.get_value(r, min_c)
                if isinstance(val, str) and (val.endswith(":") or ":" in val):
                    colon_found = True
                    break
            if colon_found:
                return True

            # If all rows have exactly 1 or 2 entries, likely metadata
            all_sparse = all(self.grid.row_non_empty_count(r, min_c, max_c) <= 2 for r in chunk)
            if all_sparse:
                return True

        return False

    def _extract_metadata_row(self, row: int, min_c: int, max_c: int) -> MetadataEntry | None:
        """Extract a single key-value metadata entry from a row."""
        key_val = self.grid.get_value(row, min_c)
        if key_val is None or str(key_val).strip() == "":
            return None

        clean_key = str(key_val).strip().rstrip(":")
        val = None
        val_coord = None

        if max_c > min_c:
            for c in range(min_c + 1, max_c + 1):
                cell_val = self.grid.get_value(row, c)
                if cell_val is not None and str(cell_val).strip() != "":
                    val = cell_val
                    val_coord = f"{self._col_letter(c)}{row}"
                    break

        key_coord = f"{self._col_letter(min_c)}{row}"
        return MetadataEntry(
            key=clean_key,
            value=val,
            key_coordinate=key_coord,
            value_coordinate=val_coord,
        )

    def identify_header_band(
        self,
        table_boundary: RegionBoundary,
    ) -> tuple[list[int], int]:
        """Detect the header rows and data start row for a table region.

        Returns (header_rows, data_start_row).
        """
        min_r = table_boundary.min_row
        max_r = table_boundary.max_row
        min_c = table_boundary.min_col
        max_c = table_boundary.max_col

        header_rows: list[int] = []

        # Iterate down rows to identify contiguous header rows dominated by strings
        for r in range(min_r, max_r + 1):
            text_ratio = self.grid.row_text_ratio(r, min_c, max_c)
            data_ratio = self.grid.row_data_ratio(r, min_c, max_c)

            # A header row has a majority of text cells
            if text_ratio >= 0.6 and data_ratio < 0.4:
                header_rows.append(r)
            else:
                # First non-header row marks the start of data
                break

        # If no header row met the threshold, default to first row of the boundary
        if not header_rows:
            header_rows = [min_r]
            data_start_row = min_r + 1 if min_r < max_r else min_r
        else:
            data_start_row = header_rows[-1] + 1

        return header_rows, min(data_start_row, max_r)

    @staticmethod
    def _col_letter(col_idx: int) -> str:
        """Convert 1-indexed column number to Excel column letters."""
        result = ""
        while col_idx > 0:
            col_idx, remainder = divmod(col_idx - 1, 26)
            result = chr(65 + remainder) + result
        return result
