"""Deterministic Arrow-backed plan executor and observation reconciler."""

from __future__ import annotations

import datetime
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.enums import PlanOperationType
from src.compiler.contracts.plans import ParsePlan
from src.compiler.contracts.structure import CellDetail
from src.compiler.execution.provenance import ProvenanceTracker
from src.compiler.readers import get_reader
from src.compiler.readers.base import ExcelReader
from src.compiler.readers.date_duration import parse_duration_to_seconds
from src.compiler.structure.header_reconstructor import HeaderReconstructor
from src.compiler.structure.occupancy_grid import OccupancyGrid

MEASUREMENT_ARROW_SCHEMA = pa.schema(
    [
        ("observation_key", pa.string()),
        ("tenant_id", pa.string()),
        ("project_id", pa.string()),
        ("asset_id", pa.string()),
        ("timestamp_utc", pa.timestamp("us", tz="UTC")),
        ("signal_id", pa.string()),
        ("value", pa.float64()),
        ("raw_source_row", pa.int64()),
        ("source_file", pa.string()),
    ]
)


class ExecutionReconciliation(BaseModel):
    """Reconciliation metrics ensuring zero silent dropping or Cartesian multiplication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    extracted_source_rows: int = Field(..., ge=0)
    data_rows_processed: int = Field(..., ge=0)
    signals_unpivoted: int = Field(..., ge=0)
    expected_emitted_records: int = Field(..., ge=0)
    actual_emitted_records: int = Field(..., ge=0)
    null_value_count: int = Field(default=0, ge=0)
    reconciliation_hash: str = Field(..., description="Canonical SHA-256 hash of long outputs.")


class ExecutionResult(BaseModel):
    """Result payload from executing a ParsePlan."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    measurements_table: pa.Table
    provenance_table: pa.Table
    reconciliation: ExecutionReconciliation


class PlanExecutor:
    """Executes declarative ParsePlans via allowlisted deterministic operations."""

    def __init__(self, reader: ExcelReader | None = None) -> None:
        self.reader = reader or get_reader()

    def execute(
        self,
        source: bytes | Path,
        plan: ParsePlan,
        source_filename: str | None = None,
        default_asset_id: str = "DEFAULT_ASSET",
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Run compiled plan against source spreadsheet and emit Arrow tables."""
        if isinstance(source, Path):
            source_file = source_filename or source.name
        else:
            source_file = source_filename or "in_memory.xlsx"

        # 1. Stream all raw cells from target sheet
        cell_batches = self.reader.extract_sheet_cells(source, plan.target_sheet)
        raw_cells: list[CellDetail] = [cell for batch in cell_batches for cell in batch]

        # Map operations by type
        ops_by_type = {op.op: op.params for op in plan.operations}

        # Operation: select_region
        select_p = ops_by_type.get(PlanOperationType.SELECT_REGION)
        if select_p:
            min_r = select_p["min_row"]
            max_r = select_p["max_row"]
            min_c = select_p["min_col"]
            max_c = select_p["max_col"]
        else:
            min_r = min((c.row for c in raw_cells), default=1)
            max_r = max((c.row for c in raw_cells), default=1)
            min_c = min((c.column for c in raw_cells), default=1)
            max_c = max((c.column for c in raw_cells), default=1)

        extracted_source_rows = max_r - min_r + 1

        bounded_cells = [
            c for c in raw_cells if min_r <= c.row <= max_r and min_c <= c.column <= max_c
        ]

        # Operation: flatten_headers
        flatten_p = ops_by_type.get(PlanOperationType.FLATTEN_HEADERS, {})
        header_rows: list[int] = flatten_p.get("header_rows", [min_r])
        data_start_row = max(header_rows) + 1

        # Use HeaderReconstructor to resolve column paths
        merged_ranges_detected = [f"{c.coordinate}" for c in bounded_cells if c.is_merged]
        # We need original merged ranges from sheet structure
        grid = OccupancyGrid(
            max_row=max_r,
            max_col=max_c,
            cells=bounded_cells,
            merged_ranges=merged_ranges_detected,
        )
        reconstructor = HeaderReconstructor(grid)
        header_paths = reconstructor.reconstruct_headers(
            header_rows=header_rows,
            min_col=min_c,
            max_col=max_c,
        )
        path_to_col: dict[str, int] = {hp.path: hp.column_index for hp in header_paths}

        # Index data cells by (row, col)
        data_cells_by_row: dict[int, dict[int, CellDetail]] = defaultdict(dict)
        for c in bounded_cells:
            if c.row >= data_start_row:
                data_cells_by_row[c.row][c.column] = c

        # Operation: filter_rows
        filter_p = ops_by_type.get(PlanOperationType.FILTER_ROWS, {})
        drop_empty = filter_p.get("drop_empty_rows", True)

        active_data_rows: list[int] = []
        for r in range(data_start_row, max_r + 1):
            row_cells = data_cells_by_row.get(r, {})
            if drop_empty:
                # Row is non-empty if at least one cell has a value
                has_val = any(
                    c.raw_value is not None and str(c.raw_value).strip() != ""
                    for c in row_cells.values()
                )
                if has_val:
                    active_data_rows.append(r)
            else:
                active_data_rows.append(r)

        data_rows_processed = len(active_data_rows)

        # Operation: unpivot
        unpivot_p = ops_by_type.get(PlanOperationType.UNPIVOT, {})
        id_vars: list[str] = unpivot_p.get("id_vars", [])
        value_vars: list[str] = unpivot_p.get("value_vars", [])

        # Formula policy
        formula_p = ops_by_type.get(PlanOperationType.FORMULA_POLICY, {})
        formula_policy = formula_p.get("policy", "use_cached_or_fail")

        signals_unpivoted = len(value_vars)
        expected_emitted = data_rows_processed * signals_unpivoted

        # Prepare accumulators for long format table
        provenance = ProvenanceTracker()
        obs_keys: list[str] = []
        tenants: list[str] = []
        projects: list[str] = []
        assets: list[str] = []
        timestamps: list[datetime.datetime] = []
        signal_ids: list[str] = []
        values: list[float | None] = []
        raw_rows: list[int] = []
        source_files: list[str] = []

        hash_accumulator = hashlib.sha256()
        null_count = 0

        for r_idx in active_data_rows:
            row_cells = data_cells_by_row.get(r_idx, {})

            # 1. Resolve timestamp and asset
            resolved_ts = self._resolve_timestamp(row_cells, id_vars, path_to_col)
            resolved_asset = self._resolve_asset(row_cells, id_vars, path_to_col, default_asset_id)

            # Compute canonical ObservationId
            ts_str = resolved_ts.isoformat() if resolved_ts else "NONE"
            obs_raw = (
                f"{plan.tenant_id}|{plan.project_id}|{resolved_asset}|"
                f"{ts_str}|{source_file}|{r_idx}"
            )
            obs_key = hashlib.sha256(obs_raw.encode()).hexdigest()

            # 2. Emit unpivoted signal values
            for sig_name in value_vars:
                col_idx = path_to_col.get(sig_name)
                cell = row_cells.get(col_idx) if col_idx is not None else None

                raw_val = cell.raw_value if cell else None
                formula_text = cell.formula if cell else None
                cell_coord = cell.coordinate if cell else f"COL_{col_idx}_R{r_idx}"

                # Apply formula policy
                if cell and cell.data_type == "f":
                    if formula_policy == "require_literal_only":
                        raise ValueError(
                            f"Formula cell {cell_coord} rejected under require_literal_only policy."
                        )
                    effective_val = cell.cached_value
                else:
                    effective_val = raw_val

                # Parse numeric / duration value
                num_val = self._parse_numeric(effective_val, cell.data_type if cell else None)
                if num_val is None:
                    null_count += 1

                obs_keys.append(obs_key)
                tenants.append(plan.tenant_id)
                projects.append(plan.project_id)
                assets.append(resolved_asset)
                timestamps.append(resolved_ts)
                signal_ids.append(sig_name)
                values.append(num_val)
                raw_rows.append(r_idx)
                source_files.append(source_file)

                # Feed hash accumulator
                hash_accumulator.update(f"{obs_key}|{sig_name}|{num_val}".encode())

                # Record coordinate provenance
                provenance.record(
                    observation_key=obs_key,
                    signal_id=sig_name,
                    source_file=source_file,
                    sheet_name=plan.target_sheet,
                    cell_coordinate=cell_coord,
                    raw_value=raw_val,
                    formula=formula_text,
                    transform_ref="unpivot",
                )

        actual_emitted = len(obs_keys)
        reconciliation_hash = hash_accumulator.hexdigest()

        reconciliation = ExecutionReconciliation(
            extracted_source_rows=extracted_source_rows,
            data_rows_processed=data_rows_processed,
            signals_unpivoted=signals_unpivoted,
            expected_emitted_records=expected_emitted,
            actual_emitted_records=actual_emitted,
            null_value_count=null_count,
            reconciliation_hash=reconciliation_hash,
        )

        measurements_table = pa.Table.from_arrays(
            [
                pa.array(obs_keys, type=pa.string()),
                pa.array(tenants, type=pa.string()),
                pa.array(projects, type=pa.string()),
                pa.array(assets, type=pa.string()),
                pa.array(timestamps, type=pa.timestamp("us", tz="UTC")),
                pa.array(signal_ids, type=pa.string()),
                pa.array(values, type=pa.float64()),
                pa.array(raw_rows, type=pa.int64()),
                pa.array(source_files, type=pa.string()),
            ],
            schema=MEASUREMENT_ARROW_SCHEMA,
        )

        return ExecutionResult(
            measurements_table=measurements_table,
            provenance_table=provenance.to_arrow(),
            reconciliation=reconciliation,
        )

    def _resolve_timestamp(
        self,
        row_cells: dict[int, CellDetail],
        id_vars: list[str],
        path_to_col: dict[str, int],
    ) -> datetime.datetime:
        """Resolve and combine date and time columns into UTC datetime."""
        date_col_name: str | None = None
        time_col_name: str | None = None
        combined_col_name: str | None = None

        for var_name in id_vars:
            upper_name = var_name.upper()

            # Check if this single column contains both DATE and TIME tokens or timestamp markers
            if ("DATE" in upper_name and "TIME" in upper_name) or any(
                k in upper_name for k in ("TIMESTAMP", "DATETIME", "UTC")
            ):
                if combined_col_name is None:
                    combined_col_name = var_name
            elif "TIME" in upper_name and "DATE" not in upper_name:
                if time_col_name is None:
                    time_col_name = var_name
            elif "DATE" in upper_name and "TIME" not in upper_name:
                if date_col_name is None:
                    date_col_name = var_name

        # 1. If a combined column exists, parse it directly as a single datetime
        if combined_col_name is not None:
            col = path_to_col.get(combined_col_name)
            cell = row_cells.get(col) if col is not None else None
            if cell and cell.raw_value is not None:
                dt = self._parse_iso_or_datetime(cell.raw_value)
                if dt is not None:
                    return dt

        # 2. If separate date and time columns exist on distinct columns
        if (
            date_col_name is not None
            and time_col_name is not None
            and date_col_name != time_col_name
        ):
            col_d = path_to_col.get(date_col_name)
            col_t = path_to_col.get(time_col_name)
            cell_d = row_cells.get(col_d) if col_d is not None else None
            cell_t = row_cells.get(col_t) if col_t is not None else None
            if cell_d and cell_d.raw_value is not None and cell_t and cell_t.raw_value is not None:
                d_val = cell_d.raw_value
                t_val = cell_t.raw_value
                if isinstance(d_val, datetime.datetime) and (
                    d_val.hour != 0 or d_val.minute != 0 or d_val.second != 0
                ):
                    return d_val if d_val.tzinfo else d_val.replace(tzinfo=datetime.UTC)
                date_str = str(d_val).split("T")[0].split(" ")[0].strip()
                time_str = str(t_val).strip()
                if isinstance(t_val, datetime.time):
                    time_str = t_val.isoformat()
                dt_str = (
                    f"{date_str}T{time_str}Z"
                    if not time_str.endswith("Z")
                    else f"{date_str}T{time_str}"
                )
                try:
                    dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.UTC)
                except ValueError:
                    pass

        # 3. Fallback to date column only if present
        if date_col_name is not None:
            col = path_to_col.get(date_col_name)
            cell = row_cells.get(col) if col is not None else None
            if cell and cell.raw_value is not None:
                dt = self._parse_iso_or_datetime(cell.raw_value)
                if dt is not None:
                    return dt

        # Fallback to epoch 1970
        return datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)

    def _parse_iso_or_datetime(self, val: Any) -> datetime.datetime | None:
        """Parse scalar raw value into UTC datetime."""
        if val is None:
            return None
        if isinstance(val, datetime.datetime):
            return val if val.tzinfo else val.replace(tzinfo=datetime.UTC)
        if isinstance(val, datetime.date):
            return datetime.datetime(val.year, val.month, val.day, tzinfo=datetime.UTC)

        val_str = str(val).strip()
        if not val_str:
            return None

        # Normalize space to T
        normalized = val_str.replace(" ", "T")
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            dt = datetime.datetime.fromisoformat(normalized)
            return dt if dt.tzinfo else dt.replace(tzinfo=datetime.UTC)
        except ValueError:
            pass

        # Try appending UTC timezone if no tz present
        if "+" not in normalized and "-" not in normalized[10:]:
            try:
                dt = datetime.datetime.fromisoformat(normalized + "+00:00")
                return dt
            except ValueError:
                pass

        return None

    def _resolve_asset(
        self,
        row_cells: dict[int, CellDetail],
        id_vars: list[str],
        path_to_col: dict[str, int],
        default_asset_id: str,
    ) -> str:
        """Resolve canonical asset identifier from row columns or fallback."""
        for var_name in id_vars:
            upper = var_name.upper()
            if any(k in upper for k in ("ASSET", "EQUIPMENT", "COMPRESSOR", "MACHINE")):
                col = path_to_col.get(var_name)
                cell = row_cells.get(col) if col is not None else None
                if cell and cell.raw_value is not None:
                    return str(cell.raw_value).strip()
        return default_asset_id

    def _parse_numeric(self, value: Any, data_type: str | None) -> float | None:
        """Convert scalar value to float, handling duration serials."""
        if value is None or str(value).strip() == "":
            return None

        if data_type == "duration":
            dur = parse_duration_to_seconds(value)
            return dur

        if isinstance(value, (int, float)):
            return float(value)

        try:
            return float(str(value).strip().replace(",", ""))
        except ValueError:
            return None
