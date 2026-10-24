"""Three-level validation engine verifying ParsePlans across SCHEMA, SEMANTICS, and EVIDENCE."""

from __future__ import annotations

import re
from pathlib import Path

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import (
    ErrorCode,
    JobResultState,
    PlanOperationType,
)
from src.compiler.contracts.plans import ParsePlan
from src.compiler.contracts.structure import CellDetail
from src.compiler.contracts.validation import PlanValidationIssue, PlanValidationReport
from src.compiler.execution.executor import PlanExecutor
from src.compiler.plans.operations import validate_operation_params
from src.compiler.readers import get_reader
from src.compiler.readers.base import ExcelReader
from src.compiler.structure.types import DiscoveredLayout
from src.compiler.validation.gate import ClientValidationGate


class PlanValidator:
    """Three-level verification engine for candidate ParsePlans.

    Evaluates a plan through:
      Level 1: SCHEMA (validates operation parameter models, forbids extra keys)
      Level 2: SEMANTICS (checks column existence, range sanity, unpivot disjointness, date tokens)
      Level 3: EVIDENCE (in-memory execution, reconciliation, provenance completeness, client gates,
                         and zero-silent-coercion enforcement)
    """

    def __init__(
        self,
        executor: PlanExecutor | None = None,
        gate: ClientValidationGate | None = None,
        reader: ExcelReader | None = None,
    ) -> None:
        self.reader = reader or get_reader()
        self.executor = executor or PlanExecutor(reader=self.reader)
        self.gate = gate or ClientValidationGate()

    def validate(
        self,
        plan: ParsePlan,
        source: bytes | Path,
        contract: ClientContract | None = None,
        layout: DiscoveredLayout | None = None,
        source_filename: str | None = None,
        default_asset_id: str = "DEFAULT_ASSET",
    ) -> PlanValidationReport:
        """Execute the 3-level verification pipeline and return an immutable report."""
        issues: list[PlanValidationIssue] = []

        # ---------------------------------------------------------
        # LEVEL 1: SCHEMA
        # ---------------------------------------------------------
        schema_issues = self._validate_schema(plan)
        if schema_issues:
            issues.extend(schema_issues)
            return PlanValidationReport(
                plan_id=plan.plan_id,
                status=JobResultState.REVIEW_REQUIRED,
                issues=issues,
                schema_passed=False,
                semantics_passed=False,
                evidence_passed=False,
            )

        # ---------------------------------------------------------
        # LEVEL 2: SEMANTICS
        # ---------------------------------------------------------
        semantics_issues = self._validate_semantics(plan, source, layout)
        if semantics_issues:
            issues.extend(semantics_issues)
            return PlanValidationReport(
                plan_id=plan.plan_id,
                status=JobResultState.REVIEW_REQUIRED,
                issues=issues,
                schema_passed=True,
                semantics_passed=False,
                evidence_passed=False,
            )

        # ---------------------------------------------------------
        # LEVEL 3: EVIDENCE
        # ---------------------------------------------------------
        evidence_issues = self._validate_evidence(
            plan=plan,
            source=source,
            contract=contract,
            layout=layout,
            source_filename=source_filename,
            default_asset_id=default_asset_id,
        )
        if evidence_issues:
            issues.extend(evidence_issues)
            return PlanValidationReport(
                plan_id=plan.plan_id,
                status=JobResultState.REVIEW_REQUIRED,
                issues=issues,
                schema_passed=True,
                semantics_passed=True,
                evidence_passed=False,
            )

        return PlanValidationReport(
            plan_id=plan.plan_id,
            status=JobResultState.ACCEPTED,
            issues=[],
            schema_passed=True,
            semantics_passed=True,
            evidence_passed=True,
        )

    def _validate_schema(self, plan: ParsePlan) -> list[PlanValidationIssue]:
        """Level 1: Validate parameter schemas for each allowlisted operation."""
        issues: list[PlanValidationIssue] = []
        for op in plan.operations:
            try:
                validate_operation_params(op.op, op.params)
            except Exception as exc:
                issues.append(
                    PlanValidationIssue(
                        level="SCHEMA",
                        code=ErrorCode.ERR_VAL_SCHEMA_VIOLATION,
                        message=f"Schema violation in operation '{op.op}': {exc}",
                    )
                )
        return issues

    def _validate_semantics(
        self,
        plan: ParsePlan,
        source: bytes | Path,
        layout: DiscoveredLayout | None,
    ) -> list[PlanValidationIssue]:
        """Level 2: Validate semantic relationships, column bounds, and ambiguity."""
        issues: list[PlanValidationIssue] = []
        ops_by_type = {op.op: op.params for op in plan.operations}

        # SEM-003 & Boundary Check: select_region
        select_p = ops_by_type.get(PlanOperationType.SELECT_REGION)
        if select_p:
            min_r = select_p.get("min_row", 1)
            max_r = select_p.get("max_row", 1)
            min_c = select_p.get("min_col", 1)
            max_c = select_p.get("max_col", 1)
            if min_r > max_r or min_c > max_c:
                issues.append(
                    PlanValidationIssue(
                        level="SEMANTICS",
                        code=ErrorCode.ERR_EXEC_INVALID_RANGE,
                        message=(
                            f"Inverted region boundaries: rows {min_r}..{max_r}, "
                            f"cols {min_c}..{max_c}"
                        ),
                    )
                )

        # SEM-004: UNPIVOT disjointness
        unpivot_p = ops_by_type.get(PlanOperationType.UNPIVOT)
        if unpivot_p:
            id_vars = set(unpivot_p.get("id_vars", []))
            value_vars = set(unpivot_p.get("value_vars", []))
            overlap = id_vars.intersection(value_vars)
            if overlap:
                issues.append(
                    PlanValidationIssue(
                        level="SEMANTICS",
                        code=ErrorCode.ERR_STRUCT_DUPLICATE_COLUMNS,
                        message=(
                            "UNPIVOT id_vars and value_vars must be disjoint. "
                            f"Overlapping: {sorted(overlap)}"
                        ),
                    )
                )

        # SEM-002: Column reference validity (TypeCast and Duration columns exist)
        type_cast_p = ops_by_type.get(PlanOperationType.TYPE_CAST)
        known_columns: set[str] = set()
        if layout and layout.tables:
            for table in layout.tables:
                for col in table.columns:
                    known_columns.add(col.path)
        if unpivot_p:
            known_columns.update(unpivot_p.get("id_vars", []))
            known_columns.update(unpivot_p.get("value_vars", []))

        if known_columns and type_cast_p:
            casts = type_cast_p.get("casts", {})
            for col_name in casts:
                if col_name not in known_columns:
                    issues.append(
                        PlanValidationIssue(
                            level="SEMANTICS",
                            code=ErrorCode.ERR_VAL_SCHEMA_VIOLATION,
                            message=f"TYPE_CAST references unknown column '{col_name}'",
                            target_column=col_name,
                        )
                    )

        duration_p = ops_by_type.get(PlanOperationType.PARSE_DURATION)
        if known_columns and duration_p:
            for col_name in duration_p.get("columns", []):
                if col_name not in known_columns:
                    issues.append(
                        PlanValidationIssue(
                            level="SEMANTICS",
                            code=ErrorCode.ERR_VAL_SCHEMA_VIOLATION,
                            message=f"PARSE_DURATION references unknown column '{col_name}'",
                            target_column=col_name,
                        )
                    )

        # SEM-001: Date token ambiguity check
        # Inspect sample cells for ambiguous formats (e.g. DD/MM vs MM/DD)
        if select_p:
            cell_batches = self.reader.extract_sheet_cells(source, plan.target_sheet)
            raw_cells: list[CellDetail] = [cell for batch in cell_batches for cell in batch]
            for c in raw_cells[:50]:
                if c.raw_value and isinstance(c.raw_value, str):
                    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", c.raw_value.strip())
                    if m:
                        n1, n2 = int(m.group(1)), int(m.group(2))
                        if 1 <= n1 <= 12 and 1 <= n2 <= 12 and n1 != n2:
                            issues.append(
                                PlanValidationIssue(
                                    level="SEMANTICS",
                                    code=ErrorCode.ERR_STRUCT_AMBIGUOUS_HEADER,
                                    message=(
                                        f"Ambiguous date '{c.raw_value}' in cell {c.coordinate}. "
                                        "Cannot determine date order without contract spec."
                                    ),
                                    source_reference=f"{plan.target_sheet}!{c.coordinate}",
                                )
                            )
                            break

        return issues

    def _validate_evidence(
        self,
        plan: ParsePlan,
        source: bytes | Path,
        contract: ClientContract | None,
        layout: DiscoveredLayout | None,
        source_filename: str | None,
        default_asset_id: str,
    ) -> list[PlanValidationIssue]:
        """Level 3: In-memory execution, reconciliation, provenance, and zero-silent-coercion."""
        issues: list[PlanValidationIssue] = []

        try:
            exec_result = self.executor.execute(
                source=source,
                plan=plan,
                source_filename=source_filename,
                default_asset_id=default_asset_id,
            )
        except Exception as exc:
            issues.append(
                PlanValidationIssue(
                    level="EVIDENCE",
                    code=ErrorCode.ERR_EXEC_PARTIAL_RESULT,
                    message=f"Execution error during evidence validation: {exc}",
                )
            )
            return issues

        # EVD-001: Row count reconciliation
        rec = exec_result.reconciliation
        if rec.data_rows_processed > 0 and rec.actual_emitted_records == 0:
            issues.append(
                PlanValidationIssue(
                    level="EVIDENCE",
                    code=ErrorCode.ERR_EXEC_PARTIAL_RESULT,
                    message=(
                        f"Zero records emitted despite processing "
                        f"{rec.data_rows_processed} data rows"
                    ),
                )
            )

        # EVD-002: Cell Provenance completeness
        prov_table = exec_result.provenance_table
        if prov_table.num_rows > 0:
            coord_col = prov_table.column("cell_coordinate")
            null_coords = coord_col.null_count
            completeness = 1.0 - (null_coords / prov_table.num_rows)
            if completeness < 1.00:
                issues.append(
                    PlanValidationIssue(
                        level="EVIDENCE",
                        code=ErrorCode.ERR_VAL_SCHEMA_VIOLATION,
                        message=(
                            f"Incomplete provenance: {null_coords} rows missing source "
                            f"cell coordinate (completeness: {completeness:.2%})"
                        ),
                    )
                )

        # EVD-004: Zero Silent Coercion
        # Verify that non-empty cells in the measurement table weren't converted silently to null
        meas_table = exec_result.measurements_table
        if meas_table.num_rows > 0:
            val_col = meas_table.column("value")
            # If all values are null or disproportionately null compared to processed cells
            if val_col.null_count == meas_table.num_rows:
                issues.append(
                    PlanValidationIssue(
                        level="EVIDENCE",
                        code=ErrorCode.ERR_VAL_SCHEMA_VIOLATION,
                        message=(
                            "Silent coercion failure: all unpivoted measurement "
                            "values evaluated to null"
                        ),
                    )
                )

        # EVD-003: ClientContract Gate Evaluation
        if contract is not None:
            gate_rep = self.gate.validate(
                execution_result=exec_result,
                contract=contract,
                target_object_id=source_filename or "in_memory.xlsx",
                discovered_layout=layout,
            )
            if gate_rep.result_state != JobResultState.ACCEPTED:
                for err in gate_rep.errors:
                    issues.append(
                        PlanValidationIssue(
                            level="EVIDENCE",
                            code=err.code,
                            message=err.message,
                            source_reference=err.cell_coordinate,
                        )
                    )

        return issues
