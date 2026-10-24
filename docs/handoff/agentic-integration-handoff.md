# Technical Handoff: AICONNEX Industrial Excel Compiler
## Architecture, Contracts, Interfaces, and Integration Handoff for Deep Agents + Sandbox Layer

**Document ID:** `DOC-HANDOFF-2026-10-24-AGENTIC-INTEGRATION`  
**Target Audience:** External Architecture Team & Agent Engineers  
**Target Integration:** Deep Agents + Docker Sandbox Investigation Layer  
**Repository Working Directory:** `x:\data-compiler`  
**Governing Standard:** `AGENTS.md` (Untrusted Data Boundary, Zero Silent Errors, Full Deterministic Provenance)  
**Verification Baseline:** 114 / 114 Unit & Integration Tests Passing (`uv run pytest -q`)

---

## SECTION 1 — Repository Map (Facts Only)

### 1.1 Directory Tree (2 Levels Deep)

```
x:\data-compiler\
├── .agent/                     # Antigravity agent configuration and skill definitions
│   └── skills/                 # Agent operational skills
├── .agents/                    # Specialized agent capability modules
│   └── skills/                 # Workflow skills (GSD, mapper, etc.)
├── .gemini/                    # Gemini workspace metadata
├── docs/                       # Architecture specifications and documentation
│   ├── adr/                    # Architecture Decision Records (ADR-001 to ADR-014)
│   ├── handoff/                # Handoff documents for external systems
│   └── specs/                  # Phase design specifications (Phases 0 to 10)
├── src/                        # Production source code
│   └── compiler/               # Core compiler package
│       ├── admission/          # Archive safety, traversal, and zip bomb validation
│       ├── contracts/          # Strict Pydantic v2 schemas and system boundaries
│       ├── execution/          # Deterministic plan executor & Arrow provenance tracker
│       ├── investigation/      # Phase 8 read-only bounded agent (dormant)
│       ├── plans/              # Plan operations, schemas, and parameter validation
│       ├── readers/            # Workbook intake engines (Openpyxl)
│       ├── recipes/            # Recipe registry, signature hashing & drift detection
│       ├── reconciliation/     # Cross-file batch assembly & temporal alignment
│       ├── storage/            # Object storage abstractions & local filesystem implementation
│       ├── structure/          # Layout discovery, region extraction & ambiguity scoring
│       ├── validation/         # Multi-layer domain validation gates & reports
│       └── workflows/          # Durable workflow engine, activities & outbox
└── tests/                      # Verification suite
    ├── conftest.py             # Shared pytest fixtures
    ├── golden/                 # End-to-end evaluation runner and golden benchmarks
    ├── integration/            # Cross-component workflow and storage integration tests
    └── unit/                   # Isolated unit tests covering all compiler modules
```

### 1.2 Package Purpose Reference Table

| Package | Relative Path | Purpose |
|---|---|---|
| **Contracts** | `src/compiler/contracts/` | Canonical Pydantic data contracts (plans, manifests, structure, validation, recipes). |
| **Admission** | `src/compiler/admission/` | Validates archive integrity, zip bombs, directory traversal, and size limits. |
| **Readers** | `src/compiler/readers/` | Reads raw Excel bytes into memory grids using `openpyxl`. |
| **Structure** | `src/compiler/structure/` | Occupancy grid discovery, table/metadata region detection, header hierarchy reconstruction, ambiguity scoring. |
| **Plans** | `src/compiler/plans/` | Operation definitions, schemas, and parameter validation rules. |
| **Execution** | `src/compiler/execution/` | Executes allowlisted plan operations and records Arrow-backed cell-level provenance. |
| **Validation** | `src/compiler/validation/` | Client contract validation gate (temporal monotonic, signal boundaries, asset identity). |
| **Recipes** | `src/compiler/recipes/` | Signature hashing, drift detection, and persistent recipe storage. |
| **Reconciliation**| `src/compiler/reconciliation/`| Batch assembly across multi-file archives, cross-file deduplication and cadence matching. |
| **Storage** | `src/compiler/storage/` | Abstract object storage interface and local directory implementation. |
| **Investigation** | `src/compiler/investigation/`| Read-only bounded LLM agent tools, budget tracker, and mock client (dormant). |
| **Workflows** | `src/compiler/workflows/` | State machine engine, activities, and idempotent outbox pattern store. |
| **Tests** | `tests/` | 114 test files across `unit/`, `integration/`, and `golden/`. |
| **Fixtures** | `tests/golden/fixtures/` | Synthetic CSV/Excel datasets and golden ground truth definitions. |

### 1.3 Python Version, Package Manager, and Quoted `pyproject.toml`

- **Python Version:** `>=3.11` (Runtime executed under Python 3.12.3 via `uv`)
- **Dependency Manager:** `uv`

Exact content of `pyproject.toml` `[project]` dependencies list quoted directly from `x:\data-compiler\pyproject.toml`:

```toml
[project]
name = "data-compiler"
version = "0.1.0"
description = "AICONNEX Industrial Excel Compiler"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "openpyxl>=3.1.5",
    "pydantic>=2.9.0",
    "pyarrow>=17.0.0",
    "pydantic-settings>=2.5.0",
    "python-multipart>=0.0.12",
    "pyyaml>=6.0.2",
    "uvicorn>=0.30.0",
]
```

---

## SECTION 2 — The ParsePlan Contract (Exact)

### 2.1 Full Definition of `ParsePlan` and `PlanOperation`

Source: `src/compiler/contracts/plans.py` (Lines 1–90)

```python
"""ParsePlan schema and operation contracts."""

from __future__ import annotations

import datetime
from typing import Any
from pydantic import Field, field_validator

from src.compiler.contracts.base import BaseContract
from src.compiler.contracts.enums import PlanOperationType

SCHEMA_VERSION = "1.0.0"


class PlanOperation(BaseContract):
    """A single deterministic operation within a ParsePlan."""

    op: PlanOperationType = Field(
        ...,
        description="The allowlisted operation to perform.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific parameters. Must conform to the operation's schema.",
    )
    description: str | None = Field(
        None,
        description="Human-readable description of why this operation is in the plan.",
    )


class ParsePlan(BaseContract):
    """A complete, validated, declarative recipe for transforming an Excel sheet

    into an industrial time-series table.
    """

    schema_version: str = Field(
        SCHEMA_VERSION,
        description="Schema version of this ParsePlan contract.",
    )
    plan_id: str = Field(
        ...,
        description="Unique identifier for this plan (e.g. UUID4).",
    )
    sheet_name: str = Field(
        ...,
        description="The exact sheet name within the workbook this plan applies to.",
    )
    header_rows: list[int] = Field(
        ...,
        min_length=1,
        description="0-based row indices that constitute the header band.",
    )
    data_start_row: int = Field(
        ...,
        ge=0,
        description="0-based row index where data rows begin.",
    )
    data_end_row: int | None = Field(
        None,
        ge=0,
        description="0-based row index where data rows end (inclusive). None = auto-detect.",
    )
    operations: list[PlanOperation] = Field(
        default_factory=list,
        description="Ordered sequence of operations to apply to the data table.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted or declared metadata (asset_id, timestamps, etc.).",
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        description="Timestamp when this plan was generated.",
    )
    created_by: str = Field(
        ...,
        description="Origin of the plan: 'discovery', 'recipe:<id>', or 'human:<id>'.",
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema version: {v}. Expected: {SCHEMA_VERSION}")
        return v

    @field_validator("data_start_row")
    @classmethod
    def validate_data_start_after_headers(cls, v: int, info: Any) -> int:
        header_rows = info.data.get("header_rows")
        if header_rows and v <= max(header_rows):
            raise ValueError(
                f"data_start_row ({v}) must be greater than all header_rows ({header_rows})"
            )
        return v
```

### 2.2 Base Contract Rules
Source: `src/compiler/contracts/base.py`

```python
class BaseContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )
```
*Notice:* Every contract has `extra="forbid"` and `frozen=True`. No undeclared fields can pass validation.

### 2.3 Allowlisted Operations Enumeration

Source: `src/compiler/contracts/enums.py`

```python
class PlanOperationType(str, Enum):
    EXTRACT_METADATA = "extract_metadata"
    SET_HEADER_BAND = "set_header_band"
    COLLAPSE_HEADER_HIERARCHY = "collapse_header_hierarchy"
    UNMERGE_FILL = "unmerge_fill"
    FORWARD_FILL = "forward_fill"
    CONVERT_TYPES = "convert_types"
    DROP_EMPTY_ROWS = "drop_empty_rows"
    FILTER_BY_REGEX = "filter_by_regex"
    TRANSPOSE = "transpose"
    UNPIVOT = "unpivot"
```

Source: `src/compiler/plans/operations.py` (Parameter Schemas & Allowlist Enforcement)

```python
OPERATION_SCHEMAS: dict[PlanOperationType, dict[str, Any]] = {
    PlanOperationType.EXTRACT_METADATA: {
        "required": ["cells"],
        "properties": {
            "cells": {"type": "list"},
            "strategy": {"type": "str", "default": "exact_cell"},
        },
    },
    PlanOperationType.SET_HEADER_BAND: {
        "required": ["rows"],
        "properties": {
            "rows": {"type": "list"},
            "merge_strategy": {"type": "str", "default": "forward_fill"},
        },
    },
    PlanOperationType.COLLAPSE_HEADER_HIERARCHY: {
        "required": ["separator"],
        "properties": {
            "separator": {"type": "str", "default": "."},
            "strip_whitespace": {"type": "bool", "default": True},
        },
    },
    PlanOperationType.UNMERGE_FILL: {
        "required": ["direction"],
        "properties": {
            "direction": {"type": "str", "enum": ["down", "right"]},
            "columns": {"type": "list", "default": None},
        },
    },
    PlanOperationType.FORWARD_FILL: {
        "required": ["columns"],
        "properties": {
            "columns": {"type": "list"},
            "limit": {"type": "int", "default": None},
        },
    },
    PlanOperationType.CONVERT_TYPES: {
        "required": ["column_types"],
        "properties": {
            "column_types": {"type": "dict"},
            "datetime_formats": {"type": "dict", "default": None},
            "on_error": {"type": "str", "default": "raise"},
        },
    },
    PlanOperationType.DROP_EMPTY_ROWS: {
        "required": [],
        "properties": {
            "threshold": {"type": "float", "default": 1.0},
            "subset": {"type": "list", "default": None},
        },
    },
    PlanOperationType.FILTER_BY_REGEX: {
        "required": ["column", "pattern"],
        "properties": {
            "column": {"type": "str"},
            "pattern": {"type": "str"},
            "action": {"type": "str", "default": "keep"},
        },
    },
    PlanOperationType.TRANSPOSE: {
        "required": [],
        "properties": {
            "new_header_row": {"type": "int", "default": 0},
        },
    },
    PlanOperationType.UNPIVOT: {
        "required": ["id_vars", "value_vars"],
        "properties": {
            "id_vars": {"type": "list"},
            "value_vars": {"type": "list"},
            "var_name": {"type": "str", "default": "variable"},
            "value_name": {"type": "str", "default": "value"},
        },
    },
}
```

### 2.4 How Unknown Operations and Parameters Are Rejected

Source: `src/compiler/plans/operations.py` (Lines 94–120)

```python
def validate_operation_params(op: PlanOperation) -> list[str]:
    """Validate that an operation's parameters conform to its schema.

    Returns a list of error strings (empty if valid).
    """
    if op.op not in OPERATION_SCHEMAS:
        return [f"Unknown operation: {op.op}"]

    schema = OPERATION_SCHEMAS[op.op]
    errors: list[str] = []

    for req in schema["required"]:
        if req not in op.parameters:
            errors.append(f"Operation '{op.op.value}' missing required parameter: '{req}'")

    props = schema["properties"]
    for param_name, param_value in op.parameters.items():
        if param_name not in props:
            errors.append(f"Operation '{op.op.value}' has unknown parameter: '{param_name}'")

    return errors
```
When constructed via Pydantic (`PlanOperation(op="unknown", ...)`), Pydantic itself raises `pydantic.ValidationError` because `op` is typed as enum `PlanOperationType`. If instantiated dynamically or passed through `validate_operation_params`, an error string `"Unknown operation: ..."` is returned with `ErrorCode.SCHEMA_VALIDATION_ERROR`.

---

## SECTION 3 — Structural Representation and Discovery Failure

### 3.1 Data Model Representing Parsed Workbook Before Interpretation

Source: `src/compiler/contracts/structure.py` and `src/compiler/structure/types.py`

```python
# src/compiler/contracts/structure.py
class RegionBoundary(BaseContract):
    top_left: tuple[int, int]      # (row, col) 0-based
    bottom_right: tuple[int, int]  # (row, col) 0-based inclusive

class CellDetail(BaseContract):
    row: int
    col: int
    raw_value: Any = None
    formatted_value: str | None = None
    data_type: str = "empty"
    formula: str | None = None
    is_merged: bool = False
    merge_parent: tuple[int, int] | None = None

class SheetStructure(BaseContract):
    name: str
    total_rows: int
    total_cols: int
    occupancy_grid: list[list[int]]
    merged_ranges: list[RegionBoundary] = Field(default_factory=list)
    detected_regions: list[RegionBoundary] = Field(default_factory=list)
    ambiguity_score: float = Field(default=0.0, ge=0.0, le=1.0)

class WorkbookStructure(BaseContract):
    file_id: str
    sheets: list[SheetStructure]
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
```

And the discovered layout structure:

```python
# src/compiler/structure/types.py
@dataclass
class HeaderPath:
    column_index: int
    levels: list[str]
    collapsed: str

@dataclass
class TableRegionLayout:
    boundary: RegionBoundary
    header_rows: list[int]
    header_paths: list[HeaderPath]
    data_start_row: int
    data_end_row: int

@dataclass
class DiscoveredLayout:
    sheet_name: str
    metadata_regions: list[MetadataEntry]
    table_regions: list[TableRegionLayout]
    ambiguity_score: float
    verdict: JobResultState  # ACCEPTED or REVIEW_REQUIRED
```

### 3.2 The Function That Runs Discovery

Source: `src/compiler/structure/discovery_engine.py` (Lines 44–112)

```python
class RuleBasedDiscoveryEngine:
    def __init__(self, ambiguity_scorer: AmbiguityScorer | None = None) -> None:
        self.scorer = ambiguity_scorer or AmbiguityScorer()

    def discover_sheet(
        self,
        sheet_structure: SheetStructure,
        cells: dict[tuple[int, int], CellDetail],
    ) -> DiscoveredLayout:
        # 1. Classify regions
        classified = self._classify_regions(sheet_structure, cells)
        
        # 2. Reconstruct header hierarchies
        tables: list[TableRegionLayout] = []
        for reg in classified["tables"]:
            header_paths, data_start, data_end = self._reconstruct_table(reg, cells)
            tables.append(TableRegionLayout(
                boundary=reg,
                header_rows=[reg.top_left[0]],
                header_paths=header_paths,
                data_start_row=data_start,
                data_end_row=data_end,
            ))
            
        # 3. Score layout
        score = self.scorer.evaluate_layout(sheet_structure, tables, classified["metadata"])
        verdict = JobResultState.ACCEPTED if score < self.scorer.threshold else JobResultState.REVIEW_REQUIRED

        return DiscoveredLayout(
            sheet_name=sheet_structure.name,
            metadata_regions=classified["metadata"],
            table_regions=tables,
            ambiguity_score=score,
            verdict=verdict,
        )
```

### 3.3 The Precise Failure / Ambiguity Signal

Discovery communicates ambiguity **not by throwing an unhandled exception**, but via:
1. `DiscoveredLayout.verdict == JobResultState.REVIEW_REQUIRED`
2. `DiscoveredLayout.ambiguity_score >= 0.30`
3. If structural anomalies occur (e.g. 0 rows detected, unparseable spans), it raises `StructuralAnomalyError` or `EmptySheetError`.

### 3.4 Where the Decision "Route to Review" vs "Continue" is Made

Source: `src/compiler/workflows/activities.py` (Lines 96–112)

```python
# Quoted from src/compiler/workflows/activities.py:
for sheet_struct in workbook_struct.sheets:
    layout = self.discovery_engine.discover_sheet(sheet_struct, cells.get(sheet_struct.name, {}))
    discovered_layouts.append(layout)
    if layout.verdict != JobResultState.ACCEPTED:
        needs_review = True
        review_items.append(
            ReviewItem(
                review_id=f"rev_{uuid.uuid4().hex[:8]}",
                source_file_id=job.job_id,
                sheet_name=sheet_struct.name,
                reason=f"Structural ambiguity score: {layout.ambiguity_score:.2f} >= threshold",
                ambiguity_score=layout.ambiguity_score,
                structural_context={"detected_tables": len(layout.table_regions)},
            )
        )
```

### 3.5 The Ambiguity Scorer Inputs, Outputs, and Threshold

Source: `src/compiler/structure/ambiguity_scorer.py` (Lines 15–50)

```python
class AmbiguityScorer:
    """Evaluates the confidence/ambiguity of a discovered structural layout."""

    def __init__(self, threshold: float = 0.30) -> None:
        self.threshold = threshold

    def evaluate_layout(
        self,
        sheet_structure: SheetStructure,
        tables: list[TableRegionLayout],
        metadata: list[MetadataEntry],
    ) -> float:
        penalties = 0.0

        # Multi-table ambiguity penalty
        if len(tables) > 1:
            penalties += 0.35

        # Empty table penalty
        if not tables:
            penalties += 0.50

        # Duplicate header names penalty
        for table in tables:
            names = [p.collapsed for p in table.header_paths]
            if len(names) != len(set(names)):
                penalties += 0.40

        return min(penalties, 1.0)
```
*Threshold:* Configured at default `0.30` in `AmbiguityScorer.__init__`. A single duplicate column path immediately yields `0.40 >= 0.30`, forcing `REVIEW_REQUIRED`.

---

## SECTION 4 — The Executor Entry Point

### 4.1 Signature and Return Type

Source: `src/compiler/execution/executor.py` (Lines 35–52)

```python
class PlanExecutor:
    """Consumes an immutable ParsePlan and an in-memory WorkbookStructure

    to emit a typed, columnar Parquet table alongside Apache Arrow
    cell-level provenance metadata.
    """

    def execute(
        self,
        plan: ParsePlan,
        workbook: WorkbookStructure,
        raw_cells: dict[str, dict[tuple[int, int], CellDetail]],
        asset_id: str = "DEFAULT_ASSET",
    ) -> ExecutionResult:
```

### 4.2 Return Type Schema (`ExecutionResult`)

Source: `src/compiler/execution/executor.py` (Lines 22–32)

```python
@dataclass
class ExecutionResult:
    table: pa.Table
    provenance_table: pa.Table
    row_count: int
    column_count: int
    plan_id: str
    metadata: dict[str, Any]
```

### 4.3 `ProvenanceTracker` Interface and Arrow Schema

Source: `src/compiler/execution/provenance.py` (Lines 10–54)

```python
PROVENANCE_ARROW_SCHEMA = pa.schema([
    ("target_column", pa.string()),
    ("target_row_index", pa.int64()),
    ("source_sheet", pa.string()),
    ("source_row", pa.int64()),
    ("source_col", pa.int64()),
    ("source_cell_coordinate", pa.string()),
    ("raw_source_value", pa.string()),
    ("operation_applied", pa.string()),
])

class ProvenanceTracker:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(
        self,
        target_col: str,
        target_row: int,
        source_sheet: str,
        source_row: int,
        source_col: int,
        coord: str,
        raw_val: Any,
        operation: str = "DIRECT_EXTRACT",
    ) -> None:
        self._records.append({
            "target_column": str(target_col),
            "target_row_index": int(target_row),
            "source_sheet": str(source_sheet),
            "source_row": int(source_row),
            "source_col": int(source_col),
            "source_cell_coordinate": str(coord),
            "raw_source_value": "" if raw_val is None else str(raw_val),
            "operation_applied": str(operation),
        })

    def to_arrow_table(self) -> pa.Table:
        ...
```

### 4.4 Quoted Test Showing Construction and Execution of `ParsePlan`

Source: `tests/unit/execution/test_executor_simple.py` (Lines 18–68)

```python
def test_plan_executor_simple_matrix() -> None:
    # Setup test cells
    cells = {
        (0, 0): CellDetail(row=0, col=0, raw_value="TIMESTAMP", data_type="string"),
        (0, 1): CellDetail(row=0, col=1, raw_value="TEMPERATURE", data_type="string"),
        (0, 2): CellDetail(row=0, col=2, raw_value="PRESSURE", data_type="string"),
        (1, 0): CellDetail(row=1, col=0, raw_value="2026-03-01T00:00:00Z", data_type="string"),
        (1, 1): CellDetail(row=1, col=1, raw_value="45.2", data_type="numeric"),
        (1, 2): CellDetail(row=1, col=2, raw_value="101.3", data_type="numeric"),
        (2, 0): CellDetail(row=2, col=0, raw_value="2026-03-01T00:01:00Z", data_type="string"),
        (2, 1): CellDetail(row=2, col=1, raw_value="46.0", data_type="numeric"),
        (2, 2): CellDetail(row=2, col=2, raw_value="101.5", data_type="numeric"),
    }

    sheet = SheetStructure(
        name="Sheet1",
        total_rows=3,
        total_cols=3,
        occupancy_grid=[[1, 1, 1], [1, 1, 1], [1, 1, 1]],
    )
    workbook = WorkbookStructure(file_id="wb1", sheets=[sheet])

    plan = ParsePlan(
        plan_id="plan-1",
        sheet_name="Sheet1",
        header_rows=[0],
        data_start_row=1,
        data_end_row=2,
        operations=[
            PlanOperation(
                op=PlanOperationType.CONVERT_TYPES,
                parameters={
                    "column_types": {
                        "TEMPERATURE": "float",
                        "PRESSURE": "float",
                    }
                },
            )
        ],
        created_by="discovery",
    )

    executor = PlanExecutor()
    res = executor.execute(
        plan, workbook, {"Sheet1": cells}, asset_id="TURBINE-01"
    )

    assert res.row_count == 2
    assert "observation_id" in res.table.column_names
    assert "asset_id" in res.table.column_names
    assert "timestamp" in res.table.column_names
    assert "TEMPERATURE" in res.table.column_names
    assert res.provenance_table.num_rows > 0
```

---

## SECTION 5 — The Validation Gate

### 5.1 Validation Function Signature

Source: `src/compiler/validation/gate.py` (Lines 18–35)

```python
class ClientValidationGate:
    """Enforces client contract rules (temporal continuity, signal value boundaries,

    and mandatory asset identity) on compiled Arrow tables.
    """

    def validate(
        self,
        table: pa.Table,
        contract: ClientContract,
        dataset_id: str = "DEFAULT_DATASET",
    ) -> ValidationReport:
```

### 5.2 Return Type Schema (`ValidationReport`)

Source: `src/compiler/validation/reports.py` (Lines 8–35)

```python
class ValidationIssue(BaseContract):
    code: ErrorCode
    message: str
    severity: ValidationSeverity
    target_column: str | None = None
    target_row_index: int | None = None
    cell_coordinate: str | None = None
    value: Any = None

class ValidationReport(BaseContract):
    dataset_id: str
    status: JobResultState  # ACCEPTED, REVIEW_REQUIRED, or REJECTED
    total_rows_inspected: int
    issues: list[ValidationIssue] = Field(default_factory=list)
    validated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
```

### 5.3 Error Codes Taxonomy

Source: `src/compiler/contracts/enums.py` (Lines 26–65)

```python
class ErrorCode(str, Enum):
    # Admission & Integrity Errors
    FILE_CORRUPT = "E1001"
    ZIP_BOMB_DETECTED = "E1002"
    PATH_TRAVERSAL_DETECTED = "E1003"
    FILE_TOO_LARGE = "E1004"
    UNSUPPORTED_FORMAT = "E1005"

    # Structural Discovery Errors
    EMPTY_SHEET = "E2001"
    STRUCTURAL_ANOMALY = "E2002"
    AMBIGUOUS_LAYOUT = "E2003"
    HEADER_NOT_FOUND = "E2004"
    SCHEMA_VALIDATION_ERROR = "E2005"

    # Execution & Parsing Errors
    TYPE_CONVERSION_FAILED = "E3001"
    OPERATION_EXECUTION_FAILED = "E3002"
    MISSING_REQUIRED_COLUMN = "E3003"
    PROVENANCE_TRACKING_FAILED = "E3004"

    # Domain & Client Validation Errors
    TIMESTAMP_OUT_OF_BOUNDS = "E4001"
    TIMESTAMP_NOT_MONOTONIC = "E4002"
    SAMPLING_RATE_DISCONTINUITY = "E4003"
    SIGNAL_VALUE_OUT_OF_BOUNDS = "E4004"
    RATE_OF_CHANGE_EXCEEDED = "E4005"
    UNKNOWN_SIGNAL = "E4006"
    MISSING_MANDATORY_SIGNAL = "E4007"
    ASSET_ID_MISMATCH = "E4008"
```

### 5.4 Exact Decision Point for `status` Assignment

Source: `src/compiler/validation/gate.py` (Lines 68–74)

```python
        # Quoted from src/compiler/validation/gate.py (Line 69):
        status = JobResultState.ACCEPTED if not issues else JobResultState.REVIEW_REQUIRED

        return ValidationReport(
            dataset_id=dataset_id,
            status=status,
            total_rows_inspected=table.num_rows,
            issues=issues,
        )
```

---

## SECTION 6 — Phase 8 Bounded Investigation Agent — What Actually Exists

### 6.1 Status: Completely Dormant

> [!IMPORTANT]
> The Phase 8 Investigation Agent code exists in `src/compiler/investigation/`, but it is **DORMANT**.
> It is **NOT** wired into `DurableWorkflowEngine`, `activities.py`, or the FastAPI routes. Currently, when discovery yields `verdict != ACCEPTED`, `activities.py` directly creates a `ReviewItem` and routes the job to `WAITING_FOR_REVIEW`. The agent is never invoked in the live pipeline.

### 6.2 `ModelClient` Protocol and Mock

Source: `src/compiler/investigation/model_client.py` (Lines 1–65)

```python
class ModelClient(Protocol):
    """Protocol for LLM interactions ensuring testability and zero live network coupling."""

    def complete(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None = None) -> ModelResponse:
        ...

class DeterministicFakeModelClient:
    """Mock LLM client executing canned responses for reliable unit testing."""

    def __init__(self, responses: list[ModelResponse] | None = None) -> None:
        self.responses: list[ModelResponse] = responses or []
        self.call_count: int = 0
        self.history: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None = None) -> ModelResponse:
        self.history.append(messages)
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return ModelResponse(
            content="Investigation complete.",
            tool_calls=[],
            finish_reason="stop",
            usage_tokens={"prompt": 100, "completion": 50, "total": 150},
        )
```

### 6.3 Tool List Exposed to the Agent

Source: `src/compiler/investigation/tools.py` (Lines 1–130)

1. `inspect_cell(sheet_name: str, row: int, col: int) -> dict`  
   Fetches raw value, formatted value, data type, formula, and merge status for a single cell.
2. `get_region_bounding_box(sheet_name: str, region_index: int) -> dict`  
   Returns the top-left and bottom-right coordinates for a detected table or metadata region.
3. `sample_column_values(sheet_name: str, col: int, start_row: int, end_row: int, max_samples: int = 10) -> list[str]`  
   Returns non-empty cell value representations from a designated vertical column span.
4. `read_recipe(signature_hash: str) -> dict`  
   Looks up an existing recipe in the `RecipeRegistry` by structural signature hash.

### 6.4 Hard Bounds Enforced by the Agent

Source: `src/compiler/investigation/agent.py` (Lines 25–48)

- **Max Turns:** 10 interaction turns. If turn count exceeds 10, execution halts and returns reason `"BUDGET_EXCEEDED"`.
- **Max Token Budget:** 50,000 cumulative tokens. If token usage exceeds this ceiling, execution halts.
- **Max Execution Wall-Clock Time:** 60 seconds.
- **Tool Allowlist:** Only the 4 read-only diagnostic tools above can be invoked. No file modification, shell commands, or arbitrary network access.

---

## SECTION 7 — The Job State Machine and Durable Workflow

### 7.1 `JobStatus` Lifecycle Enum

Source: `src/compiler/workflows/models.py` (Lines 12–25)

```python
class JobStatus(str, Enum):
    RECEIVED = "RECEIVED"
    ADMITTED = "ADMITTED"
    INGESTING = "INGESTING"
    DISCOVERING = "DISCOVERING"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
```

### 7.2 Durable Workflow Engine Implementation

Source: `src/compiler/workflows/engine.py` (Lines 22–95)

> [!NOTE]
> The durable workflow is implemented as an **in-process Python state machine**, **not Temporal**.
> Jobs, step transitions, and pending human review items are stored in memory (`dict[str, JobRecord]`) and serialized to `ObjectStore`.

```python
class DurableWorkflowEngine:
    """In-process durable workflow engine executing sequential activities with state persistence."""

    def __init__(
        self,
        object_store: ObjectStore,
        activities: IngestionActivities | None = None,
    ) -> None:
        self.store = object_store
        self.activities = activities or IngestionActivities(object_store=self.store)
        self._jobs: dict[tuple[str, str, str], JobRecord] = {}
        self._idempotency_index: dict[str, str] = {}
```

Step execution sequence:
1. `admission_activity` -> moves job to `ADMITTED`
2. `structural_discovery_activity` -> moves job to `DISCOVERING`
3. `plan_resolution_activity` -> if ambiguous, moves job to `WAITING_FOR_REVIEW`; if resolved, moves to `EXECUTING`
4. `execution_activity` -> moves job to `VALIDATING`
5. `validation_activity` -> moves job to `PUBLISHED` (or `WAITING_FOR_REVIEW` if domain issues found)

### 7.3 Outbox Deduplication Logic

Source: `src/compiler/workflows/outbox.py` (Lines 17–30)

```python
    def emit(self, event: HandoffEvent) -> HandoffEvent:
        """Enqueue an authenticated handoff event, deduplicating via SHA-256 idempotency key."""
        idempotency_key = hashlib.sha256(
            f"{event.handoff_manifest_uri}:{event.payload_sha256}".encode()
        ).hexdigest()

        if idempotency_key in self._idempotency_map:
            existing_event_id = self._idempotency_map[idempotency_key]
            return self._events[existing_event_id]

        self._events[event.event_id] = event
        self._idempotency_map[idempotency_key] = event.event_id
        return event
```

---

## SECTION 8 — Key Contracts and Data Models (Exact Schemas)

### 8.1 `UploadManifest`
Source: `src/compiler/contracts/manifests.py` (Lines 15–32)

```python
class UploadManifest(BaseContract):
    """Manifest describing an uploaded archive or file batch submitted for ingestion."""

    manifest_id: str
    tenant_id: str
    asset_id: str
    uploaded_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    source_archive_name: str
    source_archive_sha256: str
    files: list[FileIngestionEntry]
    total_uncompressed_bytes: int
```

### 8.2 `ClientContract`
Source: `src/compiler/contracts/client.py` (Lines 8–35)

```python
class ClientContract(BaseContract):
    """Client operational expectations and validation contract for an industrial asset."""

    contract_id: str
    client_id: str
    asset_id: str
    expected_cadence_seconds: float = Field(..., gt=0)
    allowed_cadence_jitter_pct: float = Field(default=10.0, ge=0.0, le=100.0)
    signals: SignalDictionary
    asset_map: AssetMap
    timezone: str = Field(default="UTC")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
```

### 8.3 `SignalDictionary` and `AssetMap`
Source: `src/compiler/contracts/signals.py` (Lines 8–45)

```python
class SignalDefinition(BaseContract):
    name: str
    canonical_type: SignalType  # NUMERIC, DISCRETE, STATE, TIMESTAMP, STRING
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    max_rate_of_change: float | None = None
    mandatory: bool = False

class SignalDictionary(BaseContract):
    signals: dict[str, SignalDefinition]

class AssetMap(BaseContract):
    asset_id: str
    aliases: list[str] = Field(default_factory=list)
    metadata_mappings: dict[str, str] = Field(default_factory=dict)
```

### 8.4 `ObservationId`
Source: `src/compiler/contracts/observation.py` (Lines 8–30)

```python
class ObservationId(BaseContract):
    """Deterministic, collision-resistant identifier for a single time-series row."""

    asset_id: str
    timestamp_utc: datetime.datetime
    row_sequence: int = 0

    def compute_hash(self) -> str:
        payload = f"{self.asset_id}:{self.timestamp_utc.isoformat()}:{self.row_sequence}"
        return hashlib.sha256(payload.encode()).hexdigest()
```

### 8.5 `Recipe` and `StructuralSignature`
Source: `src/compiler/contracts/recipes.py` (Lines 8–36)

```python
class StructuralSignature(BaseContract):
    signature_hash: str
    sheet_name: str
    total_columns: int
    header_hash: str
    layout_type: str = "SINGLE_TABLE"

class Recipe(BaseContract):
    recipe_id: str
    structural_signature: StructuralSignature
    plan: ParsePlan
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    author: str
    is_active: bool = True
```

### 8.6 `HandoffManifest`
Source: `src/compiler/contracts/manifests.py` (Lines 35–55)

```python
class HandoffManifest(BaseContract):
    """Published dataset manifest handed off to downstream AutoMLOps."""

    manifest_id: str
    dataset_id: str
    tenant_id: str
    asset_id: str
    published_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    parquet_storage_uri: str
    provenance_storage_uri: str
    row_count: int
    column_count: int
    time_range_start: datetime.datetime
    time_range_end: datetime.datetime
    validation_status: JobResultState
    recipe_id_used: str | None = None
```

---

## SECTION 9 — Recipe Registry and Drift Detection

### 9.1 `compute_signature_hash` and `DriftDetector`

Source: `src/compiler/recipes/signatures.py` (Lines 15–72)

```python
def compute_signature_hash(
    sheet_name: str,
    total_cols: int,
    header_paths: list[str],
) -> str:
    """Compute deterministic SHA-256 structural signature hash."""
    canonical = f"{sheet_name}:{total_cols}:{':'.join(sorted(header_paths))}"
    return hashlib.sha256(canonical.encode()).hexdigest()

class DriftDetector:
    """Detects structural schema drift between incoming workbook and cached recipe."""

    def detect_drift(
        self,
        current_signature: StructuralSignature,
        cached_signature: StructuralSignature,
    ) -> DriftReport:
        is_drifted = current_signature.signature_hash != cached_signature.signature_hash
        details: list[str] = []

        if current_signature.total_columns != cached_signature.total_columns:
            details.append(
                f"Column count mismatch: {current_signature.total_columns} vs {cached_signature.total_columns}"
            )
        if current_signature.header_hash != cached_signature.header_hash:
            details.append("Header hierarchy hash mismatch.")

        return DriftReport(
            is_drifted=is_drifted,
            current_signature_hash=current_signature.signature_hash,
            cached_signature_hash=cached_signature.signature_hash,
            details=details,
        )
```

### 9.2 `RecipeRegistry`

Source: `src/compiler/recipes/registry.py` (Lines 15–50)

```python
class RecipeRegistry:
    """Thread-safe storage and lookup for operational ParsePlan recipes."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self._recipes: dict[str, Recipe] = {}
        self.storage_path = storage_path

    def register(self, recipe: Recipe) -> None:
        self._recipes[recipe.structural_signature.signature_hash] = recipe

    def lookup(self, signature_hash: str) -> Recipe | None:
        return self._recipes.get(signature_hash)
```

---

## SECTION 10 — Test Suite and Fixture Inventory

### 10.1 Test Inventory

- Total tests: **114 unit and integration tests** (100% passing).
- Run command: `uv run pytest -q`

| Directory | Scope | Test Count |
|---|---|---|
| `tests/unit/admission/` | Archive admission, zip bombs, size caps | 6 |
| `tests/unit/contracts/` | Pydantic model validation, immutability, extra="forbid" | 18 |
| `tests/unit/discovery/` | Grid occupancy, region classification, ambiguity scoring | 16 |
| `tests/unit/execution/` | Plan execution, type conversions, provenance tracking | 14 |
| `tests/unit/investigation/` | Agent budget exhaustion, tool dispatch, mock client | 8 |
| `tests/unit/recipes/` | Signature hashing, registry lookup, drift reports | 10 |
| `tests/unit/reconciliation/`| Batch assembly, deduplication, cadence alignment | 12 |
| `tests/unit/validation/` | Client validation gate, monotonic time, limits | 14 |
| `tests/integration/` | End-to-end API, durable workflow, outbox dedup | 16 |

### 10.2 Synthetic Fixtures vs Real-Client Archives

- **Synthetic Fixtures (`tests/golden/fixtures/`):**
  - Generated via openpyxl during tests. Small, deterministic tables testing specific edge cases (multi-row headers, merged blocks, regex filtering).
- **Real-Client Datasets (`X:\TAS\dataset\data\raw\`):**
  - `Dataset-TAS.zip`: 6 monthly DPR files (`DPR APR 24.xlsx` through `DPR SEP 24.xlsx`). Triggers duplicate header path `Total Gas Outlet Per Day`.
  - `suyash2.zip`: 4 SCADA files (`PNB950667`, `PNB950671`, `PNB950672`, `PNB950678`). Contains 65 signals, 26,930 rows, and 1,720,448 data cells.
  - NASA C-MAPSS: Non-Excel raw text files. Tests admission gate rejection safety.

### 10.3 Golden Evaluation Suite (`tests/golden/evaluator.py`)

Source: `tests/golden/evaluator.py` implements the evaluation protocol:
1. Feeds raw datasets through admission and discovery.
2. Compares output with expected baseline schema.
3. Computes False Acceptance Rate (FAR). Current FAR = **0.00%**.

---

## SECTION 11 — The Architecture Decision Records (ADRs)

| ADR ID | Title | Status | Impact on Agent Integration |
|---|---|---|---|
| **ADR-001** | Untrusted Data Boundary | ACCEPTED | Uploaded Excel data is data only; never interpreted as code or prompt directives. |
| **ADR-002** | Immutability of Ingestion | ACCEPTED | Original uploads stored with SHA-256 verification; no in-place mutation. |
| **ADR-003** | Zero Speculative Manipulation | ACCEPTED | No silent imputation, outlier deletion, or guessing. Missing = null. |
| **ADR-004** | Execution Safety via Allowlisted Ops | ACCEPTED | The agent may NOT propose arbitrary Python code; only allowlisted `PlanOperationType`s. |
| **ADR-005** | Per-Cell Provenance Tracking | ACCEPTED | Every compiled row/column must trace to sheet and (row, col) coordinates. |
| **ADR-006** | No Confidence-Based Acceptance | ACCEPTED | LLM confidence scores cannot bypass the validation gate. Ambiguity -> `REVIEW_REQUIRED`. |
| **ADR-007** | Dual-Engine Reader Strategy | ACCEPTED | Design called for Calamine + Openpyxl. *(Note gap: Calamine not installed).* |
| **ADR-008** | Declarative ParsePlan Contract | ACCEPTED | `ParsePlan` is the single source of truth for execution. |
| **ADR-009** | Client Contract Validation Gate | ACCEPTED | Domain validation is completely decoupled from parsing execution. |
| **ADR-010** | Recipe Registry and Drift Detection | ACCEPTED | Successful plans become recipes; drift triggers steward review. |
| **ADR-011** | Cross-File Batch Reconciliation | ACCEPTED | Batching handles multi-file archives with cadence matching. |
| **ADR-012** | Durable Workflow & Idempotent Outbox | ACCEPTED | In-process state machine with SHA-256 deduplicated events. |
| **ADR-013** | Handoff Manifest for AutoMLOps | ACCEPTED | Strict contract for downstream training pipelines. |
| **ADR-014** | Bounded Investigation Agent | ACCEPTED | LLM diagnostics strictly isolated to read-only tools and bounded budgets. |

---

## SECTION 12 — Explicit List of Stubs, Gaps, and TODOs

1. **Calamine Dependency Absent:**
   - ADR-007 specified a dual-engine reader (`python-calamine` for speed, `openpyxl` for rich formatting).
   - *Current State:* `python-calamine` is neither installed nor referenced in `pyproject.toml`. Only `OpenpyxlReader` exists in `src/compiler/readers/`.
2. **Phase 8 Investigation Agent Dormant:**
   - `src/compiler/investigation/agent.py` is implemented and unit-tested in isolation, but **zero calls exist in `workflows/activities.py`**.
   - Currently, discovery failure routes directly to `JobStatus.WAITING_FOR_REVIEW`.
3. **No Live Model Provider Integration:**
   - Only `DeterministicFakeModelClient` exists in the repository. No Anthropic, OpenAI, or Google GenAI client is wired to the agent.
4. **Standalone 3-Level Plan Validator Absent:**
   - Parameter schema validation exists in `src/compiler/plans/operations.py`, but a dedicated 3-stage validation pipeline (syntax, coordinate bounds, semantic consistency) is not broken out into a standalone module.
5. **Timestamp Resolver Header Collision Bug:**
   - In `PlanExecutor._resolve_timestamp()`, if a column is named `"DATE & TIME"`, an overly strict token collision check marks both `found_date` and `found_time` on the same column string, triggering fallback to epoch `1970-01-01`.

---

## SECTION 13 — Recommended Insertion Point for the Deep Agents + Sandbox Layer

### 13.1 Exact Insertion Point in Source Code

The designated hook point is in `src/compiler/workflows/activities.py`, specifically inside `IngestionActivities.plan_resolution_activity()`.

Current code in `src/compiler/workflows/activities.py` (Lines 96–114):

```python
        for sheet_struct in workbook_struct.sheets:
            layout = self.discovery_engine.discover_sheet(sheet_struct, cells.get(sheet_struct.name, {}))
            discovered_layouts.append(layout)
            if layout.verdict != JobResultState.ACCEPTED:
                needs_review = True
                review_items.append(
                    ReviewItem(
                        review_id=f"rev_{uuid.uuid4().hex[:8]}",
                        source_file_id=job.job_id,
                        sheet_name=sheet_struct.name,
                        reason=f"Structural ambiguity score: {layout.ambiguity_score:.2f} >= threshold",
                        ambiguity_score=layout.ambiguity_score,
                        structural_context={"detected_tables": len(layout.table_regions)},
                    )
                )
```

### 13.2 Recommended Agent Dispatch Flow

```
+-------------------------------------------------------------+
|        IngestionActivities.plan_resolution_activity         |
+-------------------------------------------------------------+
                              |
              layout.verdict != ACCEPTED ?
                              |
             +----------------+----------------+
             | YES                             | NO
             v                                 v
+-----------------------------+     +-------------------------+
| Dispatch Deep Agents        |     | Compile Discovered Plan |
| (Docker Sandbox Container)  |     +-------------------------+
+-----------------------------+
             |
   Proposes ParsePlan JSON
             |
             v
+-----------------------------+
| ParsePlan Pydantic Validate |
| (extra="forbid", allowlist) |
+-----------------------------+
             |
             +-------- Valid? --------+
             | YES                    | NO
             v                        v
+-----------------------------+     +-------------------------+
| Dry-Run in PlanExecutor     |     | Route to Human Review   |
+-----------------------------+     | (JobStatus:             |
             |                      |  WAITING_FOR_REVIEW)    |
      Execution Clean?              +-------------------------+
             |                                  ^
             +--- YES ---> [Update Job Plan]    |
             |                                  |
             +--- NO  --------------------------+
```

### 13.3 Architectural Boundary Requirements for the Sandbox Agent

1. **Input Boundary:** The sandbox receives only:
   - The raw `.xlsx` file bytes (read-only mount).
   - The `SheetStructure` JSON and detected cell occupancy grid.
   - The `ClientContract` (expected signals and cadence).
2. **Output Boundary:** The sandbox is permitted to return **only** a JSON payload conforming to the `ParsePlan` Pydantic schema.
3. **Execution Safety:** The host never executes arbitrary Python code emitted by the LLM. The proposed `ParsePlan` must be executed strictly by the deterministic `PlanExecutor`.
4. **Dry-Run Guard:** If `PlanExecutor.execute()` or `ClientValidationGate.validate()` raises an error or fails client validation, the job transitions immediately to `WAITING_FOR_REVIEW` with the agent's proposed plan attached as an unapproved draft.

---

## CONFIDENCE SECTION (Sections 2–6)

| Section | Topic | Confidence | Justification |
|---|---|---|---|
| **Section 2** | ParsePlan Contract | **HIGH** | Quoted verbatim from `src/compiler/contracts/plans.py` and `src/compiler/plans/operations.py`. Full schema and error behaviors verified against unit tests. |
| **Section 3** | Structural Discovery & Failure Signals | **HIGH** | Quoted directly from `src/compiler/structure/types.py`, `discovery_engine.py`, and `ambiguity_scorer.py`. Decision points in `activities.py` verified. |
| **Section 4** | Executor Entry Point | **HIGH** | Quoted directly from `src/compiler/execution/executor.py` and `provenance.py`. Verified with passing unit test `test_plan_executor_simple_matrix`. |
| **Section 5** | Validation Gate | **HIGH** | Quoted directly from `src/compiler/validation/gate.py` and `reports.py`. Line 69 status assignment verified against test suite. |
| **Section 6** | Phase 8 Investigation Agent Reality | **HIGH** | Quoted from `src/compiler/investigation/model_client.py` and `agent.py`. Confirmed dormant state by checking all references across `workflows/`. |
