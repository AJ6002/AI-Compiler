# ADR-009: Arrow Executor, Allowlisted Operations, and Coordinate Provenance

## Status
Accepted

## Context
Industrial spreadsheets contain tabular telemetry that must be reshaped into standardized long-format time series for machine learning and analytics. In traditional data pipelines, engineers often write arbitrary Python scripts, regex mappers, or `eval()` expressions to extract and unpivot columns.

Per AGENTS.md:
- Rule 1 & 4 (Untrusted Data Boundary & Execution Safety): Arbitrary `eval()` or `exec()` of spreadsheet cells or plan instructions is strictly forbidden.
- Rule 3 (Zero Speculative Manipulation): No silent dropping, unnotified imputation, or synthetic row multiplication.
- Rule 5 (Full Provenance): Every single emitted value must retain verifiable source provenance back to its exact coordinate and sheet name.

## Decision
1. **Allowlisted Plan Operations:**
   - Transform spreadsheets strictly through verified, deterministic operations: `select_region`, `flatten_headers`, `type_cast`, `parse_duration`, `formula_policy`, `filter_rows`, and `unpivot`.
   - Every operation is strongly typed and parameter-checked in `src/compiler/plans/operations.py`.
2. **PyArrow Tabular Engine:**
   - Compile plans into deterministic PyArrow table operations.
   - Emit measurement tables adhering to `MEASUREMENT_ARROW_SCHEMA` (`observation_key`, `tenant_id`, `project_id`, `asset_id`, `timestamp_utc`, `signal_id`, `value`, `raw_source_row`, `source_file`).
3. **Preservation of Observation Identity:**
   - Anchor observation identity at row level: `(asset_id, timestamp_utc, raw_source_row)` with SHA-256 `observation_key`.
   - Multiple signals extracted from the same source row share the same `observation_key`.
4. **Coordinate-Level Provenance Mapping:**
   - Record an auditable provenance entry for every single emitted measurement in `source-map.parquet`.
   - Link `(observation_key, signal_id)` directly to `(source_file, sheet_name, cell_coordinate, raw_value, formula)`.
5. **Reconciliation & Integrity Gate:**
   - Reconcile `actual_emitted_records == data_rows_processed * signals_unpivoted`.
   - Compute a canonical logical hash across emitted records to guarantee deterministic reproducibility.

## Consequences
- Data transformations are 100% reproducible and auditable down to individual spreadsheet cells.
- Downstream AutoMLOps consumers receive standardized Parquet datasets with cryptographic identity and lineage.
