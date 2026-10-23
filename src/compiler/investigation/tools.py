"""Sandboxed investigation tool suite with strict bounds and prompt injection guards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.compiler.contracts.enums import PlanOperationType
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.contracts.structure import WorkbookStructure
from src.compiler.plans.operations import validate_operation_params
from src.compiler.readers.formula_handler import inspect_formula_cell
from src.compiler.readers.openpyxl_reader import OpenpyxlReader

MAX_RANGE_ROWS = 50
MAX_RANGE_COLS = 20


class InvestigationToolbox:
    """Allowlisted read-only tools and proposal interface for spreadsheet investigation."""

    def __init__(
        self,
        source: bytes | Path,
        structure: WorkbookStructure,
        reader: OpenpyxlReader | None = None,
    ) -> None:
        self.source = source
        self.structure = structure
        self.reader = reader or OpenpyxlReader()
        self.proposed_plan: ParsePlan | None = None

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return provider-neutral function calling tool schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_sheets",
                    "description": "List all worksheet tab names in workbook.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "inspect_range",
                    "description": (
                        "Read raw cells within a bounded window. "
                        f"Max: {MAX_RANGE_ROWS}x{MAX_RANGE_COLS}."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sheet_name": {"type": "string"},
                            "min_row": {"type": "integer"},
                            "max_row": {"type": "integer"},
                            "min_col": {"type": "integer"},
                            "max_col": {"type": "integer"},
                        },
                        "required": ["sheet_name", "min_row", "max_row", "min_col", "max_col"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "inspect_merges",
                    "description": "Return merged cell ranges (e.g. ['B1:C1']) for a sheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {"sheet_name": {"type": "string"}},
                        "required": ["sheet_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "inspect_formula_cache",
                    "description": "Inspect formula AST string and cached evaluation for a cell.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sheet_name": {"type": "string"},
                            "coordinate": {"type": "string"},
                        },
                        "required": ["sheet_name", "coordinate"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "propose_parse_plan",
                    "description": "Propose an allowlisted ParsePlan for data extraction.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sheet_name": {"type": "string"},
                            "operations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "op": {"type": "string"},
                                        "params": {"type": "object"},
                                    },
                                    "required": ["op", "params"],
                                },
                            },
                        },
                        "required": ["sheet_name", "operations"],
                    },
                },
            },
        ]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute allowlisted tool with defensive argument clamping and untrusted sanitization."""
        if name == "list_sheets":
            sheets = [s.name for s in self.structure.sheets]
            return json.dumps({"sheets": sheets})

        if name == "inspect_merges":
            sheet_name = arguments.get("sheet_name", "")
            sheet = next((s for s in self.structure.sheets if s.name == sheet_name), None)
            if not sheet:
                return json.dumps({"error": f"Sheet '{sheet_name}' not found."})
            return json.dumps({"merged_ranges": sheet.merged_ranges})

        if name == "inspect_range":
            sheet_name = arguments.get("sheet_name", "")
            sheet = next((s for s in self.structure.sheets if s.name == sheet_name), None)
            if not sheet:
                return json.dumps({"error": f"Sheet '{sheet_name}' not found."})

            min_r = max(1, int(arguments.get("min_row", 1)))
            max_r = max(min_r, int(arguments.get("max_row", min_r)))
            min_c = max(1, int(arguments.get("min_col", 1)))
            max_c = max(min_c, int(arguments.get("max_col", min_c)))

            # Bound enforcement
            if max_r - min_r + 1 > MAX_RANGE_ROWS:
                max_r = min_r + MAX_RANGE_ROWS - 1
            if max_c - min_c + 1 > MAX_RANGE_COLS:
                max_c = min_c + MAX_RANGE_COLS - 1

            cells = [
                {
                    "coord": c.coordinate,
                    "row": c.row,
                    "col": c.column,
                    "type": c.data_type,
                    # Treat cell content strictly as untrusted data: stringify safely
                    "val": str(c.raw_value)[:100] if c.raw_value is not None else None,
                    "merged": c.is_merged,
                }
                for c in sheet.cells_sample
                if min_r <= c.row <= max_r and min_c <= c.column <= max_c
            ]
            return json.dumps({"cells": cells, "clamped_window": [min_r, max_r, min_c, max_c]})

        if name == "inspect_formula_cache":
            sheet_name = arguments.get("sheet_name", "")
            coord = arguments.get("coordinate", "").upper()
            sheet = next((s for s in self.structure.sheets if s.name == sheet_name), None)
            if not sheet:
                return json.dumps({"error": f"Sheet '{sheet_name}' not found."})

            cell = next((c for c in sheet.cells_sample if c.coordinate == coord), None)
            if not cell:
                return json.dumps({"error": f"Cell '{coord}' not found in preview sample."})

            inspection = inspect_formula_cell(cell.raw_value, cell.cached_value)
            return json.dumps(
                {
                    "coordinate": coord,
                    "has_formula": inspection.has_formula,
                    "formula": inspection.formula_text,
                    "cached_value": inspection.cached_value,
                    "is_cache_missing": inspection.is_cache_missing,
                }
            )

        if name == "propose_parse_plan":
            sheet_name = arguments.get("sheet_name", "")
            raw_ops = arguments.get("operations", [])
            validated_ops: list[PlanOperation] = []

            for op_dict in raw_ops:
                op_type_str = op_dict.get("op", "")
                try:
                    op_type = PlanOperationType(op_type_str)
                except ValueError:
                    return json.dumps({"error": f"Invalid operation '{op_type_str}'"})

                params = op_dict.get("params", {})
                try:
                    validate_operation_params(op_type, params)
                except Exception as e:
                    return json.dumps({"error": f"Invalid params for '{op_type.value}': {e!s}"})

                validated_ops.append(PlanOperation(op=op_type, params=params))

            self.proposed_plan = ParsePlan(
                tenant_id=self.structure.tenant_id,
                project_id=self.structure.project_id,
                plan_id=f"proposed_{sheet_name}",
                target_sheet=sheet_name,
                operations=validated_ops,
            )
            return json.dumps({"status": "SUCCESS", "plan_id": self.proposed_plan.plan_id})

        return json.dumps({"error": f"Unknown tool '{name}'"})
