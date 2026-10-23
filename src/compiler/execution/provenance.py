"""Coordinate-level provenance tracking and Arrow table generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field

PROVENANCE_ARROW_SCHEMA = pa.schema(
    [
        ("observation_key", pa.string()),
        ("signal_id", pa.string()),
        ("source_file", pa.string()),
        ("sheet_name", pa.string()),
        ("cell_coordinate", pa.string()),
        ("raw_value", pa.string()),
        ("formula", pa.string()),
        ("transform_ref", pa.string()),
    ]
)


class ProvenanceRecord(BaseModel):
    """Verifiable link from an emitted measurement value to its source coordinate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_key: str = Field(..., description="Observation SHA-256 key.")
    signal_id: str = Field(..., description="Canonical signal identifier.")
    source_file: str = Field(..., description="Relative source filename.")
    sheet_name: str = Field(..., description="Source worksheet tab name.")
    cell_coordinate: str = Field(..., description="A1 coordinate in source worksheet.")
    raw_value: str = Field(..., description="String representation of raw value as read.")
    formula: str | None = Field(
        default=None, description="Formula expression if cell was a formula."
    )
    transform_ref: str = Field(default="unpivot", description="Plan operation reference.")


class ProvenanceTracker:
    """Accumulates coordinate-level audit links and exports to PyArrow / Parquet."""

    def __init__(self) -> None:
        self._records: list[ProvenanceRecord] = []

    def record(
        self,
        observation_key: str,
        signal_id: str,
        source_file: str,
        sheet_name: str,
        cell_coordinate: str,
        raw_value: Any,
        formula: str | None = None,
        transform_ref: str = "unpivot",
    ) -> None:
        """Add a single cell-level provenance link."""
        raw_str = "" if raw_value is None else str(raw_value)
        self._records.append(
            ProvenanceRecord(
                observation_key=observation_key,
                signal_id=signal_id,
                source_file=source_file,
                sheet_name=sheet_name,
                cell_coordinate=cell_coordinate,
                raw_value=raw_str,
                formula=formula,
                transform_ref=transform_ref,
            )
        )

    def __len__(self) -> int:
        return len(self._records)

    def to_arrow(self) -> pa.Table:
        """Convert accumulated records to an Arrow Table matching PROVENANCE_ARROW_SCHEMA."""
        if not self._records:
            return pa.Table.from_arrays(
                [
                    pa.array([], type=pa.string()),
                    pa.array([], type=pa.string()),
                    pa.array([], type=pa.string()),
                    pa.array([], type=pa.string()),
                    pa.array([], type=pa.string()),
                    pa.array([], type=pa.string()),
                    pa.array([], type=pa.string()),
                    pa.array([], type=pa.string()),
                ],
                schema=PROVENANCE_ARROW_SCHEMA,
            )

        arrays = [
            pa.array([r.observation_key for r in self._records], type=pa.string()),
            pa.array([r.signal_id for r in self._records], type=pa.string()),
            pa.array([r.source_file for r in self._records], type=pa.string()),
            pa.array([r.sheet_name for r in self._records], type=pa.string()),
            pa.array([r.cell_coordinate for r in self._records], type=pa.string()),
            pa.array([r.raw_value for r in self._records], type=pa.string()),
            pa.array([r.formula for r in self._records], type=pa.string()),
            pa.array([r.transform_ref for r in self._records], type=pa.string()),
        ]
        return pa.Table.from_arrays(arrays, schema=PROVENANCE_ARROW_SCHEMA)

    def write_parquet(self, output_path: Path | str) -> None:
        """Serialize accumulated provenance records to Parquet format."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        table = self.to_arrow()
        pq.write_table(table, path)
