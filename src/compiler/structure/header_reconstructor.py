"""Hierarchical header path reconstruction and column disambiguation."""

from __future__ import annotations

import re

from src.compiler.structure.occupancy_grid import OccupancyGrid
from src.compiler.structure.types import HeaderPath

MERGE_RANGE_REGEX = re.compile(r"^([A-Z]+)(\d+):([A-Z]+)(\d+)$")


class HeaderReconstructor:
    """Reconstructs ordered hierarchical header paths, propagating merged ancestors."""

    def __init__(self, grid: OccupancyGrid) -> None:
        self.grid = grid
        # Map: (row, col) -> (top_left_coord, top_left_row, top_left_col)
        self._merge_map: dict[tuple[int, int], tuple[str, int, int]] = {}
        self._build_merge_map()

    def _build_merge_map(self) -> None:
        """Index merged ranges so any covered cell can look up its master cell."""
        for range_str in self.grid.merged_ranges:
            m = MERGE_RANGE_REGEX.match(range_str.strip())
            if not m:
                continue
            start_col_str, start_row_str, end_col_str, end_row_str = m.groups()
            min_c = self._col_to_num(start_col_str)
            min_r = int(start_row_str)
            max_c = self._col_to_num(end_col_str)
            max_r = int(end_row_str)

            top_left_coord = f"{start_col_str}{min_r}"
            for r in range(min_r, max_r + 1):
                for c in range(min_c, max_c + 1):
                    self._merge_map[(r, c)] = (top_left_coord, min_r, min_c)

    def reconstruct_headers(
        self,
        header_rows: list[int],
        min_col: int,
        max_col: int,
    ) -> list[HeaderPath]:
        """Construct HeaderPath for every column in the table region.

        Propagates ancestor labels from merged headers across child columns.
        """
        paths: list[HeaderPath] = []

        for c in range(min_col, max_col + 1):
            column_tokens: list[tuple[str, str]] = []  # (token_value, cell_coord)

            for r in header_rows:
                # Check if cell is part of a merge
                if (r, c) in self._merge_map:
                    top_coord, top_r, top_c = self._merge_map[(r, c)]
                    val = self.grid.get_value(top_r, top_c)
                    coord = top_coord
                else:
                    val = self.grid.get_value(r, c)
                    coord = f"{self._num_to_col(c)}{r}"

                if val is not None and str(val).strip() != "":
                    cleaned = str(val).strip()
                    # Do not append consecutive identical tokens from multi-row merges
                    if not column_tokens or column_tokens[-1][0] != cleaned:
                        column_tokens.append((cleaned, coord))

            if not column_tokens:
                # Fallback for empty header column
                fallback_name = f"COL_{self._num_to_col(c)}"
                paths.append(
                    HeaderPath(
                        column_index=c,
                        path=fallback_name,
                        leaf_name=fallback_name,
                        ancestors=[],
                        source_coordinates=[],
                    )
                )
            elif len(column_tokens) == 1:
                # Single header row
                token, coord = column_tokens[0]
                paths.append(
                    HeaderPath(
                        column_index=c,
                        path=token,
                        leaf_name=token,
                        ancestors=[],
                        source_coordinates=[coord],
                    )
                )
            else:
                # Multi-row hierarchical header
                tokens = [t[0] for t in column_tokens]
                coords = [t[1] for t in column_tokens]
                ancestors = tokens[:-1]
                leaf = tokens[-1]
                full_path = ".".join(tokens)
                paths.append(
                    HeaderPath(
                        column_index=c,
                        path=full_path,
                        leaf_name=leaf,
                        ancestors=ancestors,
                        source_coordinates=coords,
                    )
                )

        return paths

    @staticmethod
    def _col_to_num(col_str: str) -> int:
        """Convert Excel column letters (A, B, AA) to 1-indexed number."""
        num = 0
        for char in col_str.upper():
            num = num * 26 + (ord(char) - ord("A") + 1)
        return num

    @staticmethod
    def _num_to_col(col_num: int) -> str:
        """Convert 1-indexed number to Excel column letters."""
        result = ""
        while col_num > 0:
            col_num, remainder = divmod(col_num - 1, 26)
            result = chr(65 + remainder) + result
        return result
