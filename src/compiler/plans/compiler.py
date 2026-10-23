"""Plan compiler generating declarative ParsePlans from discovered structural layouts."""

from __future__ import annotations

from typing import Literal

from src.compiler.contracts.enums import PlanOperationType
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.plans.operations import validate_operation_params
from src.compiler.structure.types import DiscoveredLayout


class PlanCompiler:
    """Compiles discovered spreadsheet layouts into executable, allowlisted ParsePlans."""

    def compile(
        self,
        layout: DiscoveredLayout,
        tenant_id: str,
        project_id: str,
        table_index: int = 0,
        default_asset_id: str = "DEFAULT_ASSET",
        formula_policy: Literal[
            "use_cached_or_fail", "require_literal_only"
        ] = "use_cached_or_fail",
    ) -> ParsePlan:
        """Compile a single table layout into a validated ParsePlan."""
        if not layout.tables:
            raise ValueError(f"Sheet '{layout.sheet_name}' contains no discovered data tables.")
        if table_index >= len(layout.tables):
            raise IndexError(
                f"Table index {table_index} out of bounds ({len(layout.tables)} tables available)."
            )

        table = layout.tables[table_index]
        all_cols = [c.path for c in table.columns]

        # Identify timestamp and asset dimension columns
        timestamp_cols: list[str] = []
        asset_cols: list[str] = []
        signal_cols: list[str] = []

        for col_path in all_cols:
            upper = col_path.upper()
            if any(k in upper for k in ("TIME", "DATE", "TIMESTAMP")):
                timestamp_cols.append(col_path)
            elif any(k in upper for k in ("ASSET", "EQUIPMENT", "MACHINE")):
                asset_cols.append(col_path)
            else:
                signal_cols.append(col_path)

        # If no explicit timestamp column, fall back to first column
        if not timestamp_cols:
            timestamp_cols = [all_cols[0]]
            if all_cols[0] in signal_cols:
                signal_cols.remove(all_cols[0])

        id_vars = timestamp_cols + asset_cols
        value_vars = signal_cols

        # Fallback if all columns were classified as dimensions
        if not value_vars and len(all_cols) > 1:
            value_vars = all_cols[1:]
            id_vars = [all_cols[0]]

        # Construct allowlisted operation sequence
        ops: list[PlanOperation] = []

        # 1. Select region
        select_params = {
            "min_row": table.boundary.min_row,
            "max_row": table.boundary.max_row,
            "min_col": table.boundary.min_col,
            "max_col": table.boundary.max_col,
        }
        validate_operation_params(PlanOperationType.SELECT_REGION, select_params)
        ops.append(PlanOperation(op=PlanOperationType.SELECT_REGION, params=select_params))

        # 2. Flatten headers
        flatten_params = {
            "header_rows": table.header_rows,
            "separator": ".",
        }
        validate_operation_params(PlanOperationType.FLATTEN_HEADERS, flatten_params)
        ops.append(PlanOperation(op=PlanOperationType.FLATTEN_HEADERS, params=flatten_params))

        # 3. Formula policy
        formula_params = {"policy": formula_policy}
        validate_operation_params(PlanOperationType.FORMULA_POLICY, formula_params)
        ops.append(PlanOperation(op=PlanOperationType.FORMULA_POLICY, params=formula_params))

        # 4. Filter rows
        filter_params = {"drop_empty_rows": True, "exclude_patterns": []}
        validate_operation_params(PlanOperationType.FILTER_ROWS, filter_params)
        ops.append(PlanOperation(op=PlanOperationType.FILTER_ROWS, params=filter_params))

        # 5. Unpivot to long format
        unpivot_params = {
            "id_vars": id_vars,
            "value_vars": value_vars,
            "var_name": "signal_id",
            "value_name": "value",
        }
        validate_operation_params(PlanOperationType.UNPIVOT, unpivot_params)
        ops.append(PlanOperation(op=PlanOperationType.UNPIVOT, params=unpivot_params))

        plan_id = f"plan_{layout.sheet_name}_tbl{table_index + 1}"
        return ParsePlan(
            tenant_id=tenant_id,
            project_id=project_id,
            plan_id=plan_id,
            target_sheet=layout.sheet_name,
            operations=ops,
        )
