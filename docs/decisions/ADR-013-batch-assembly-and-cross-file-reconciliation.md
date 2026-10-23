# ADR-013: Batch Assembly and Cross-File Reconciliation

## Status
Accepted

## Context
Industrial spreadsheet ingestion frequently arrives as multi-workbook ZIP archives representing fleets of machinery (e.g. 5 compressor stations reporting daily telemetry). Processing these files requires combining individual per-file measurement tables into a cohesive batch dataset while ensuring cross-file integrity and provenance.

Furthermore:
- **AGENTS.md Rule 3 (Zero Speculative Manipulation):** When two files provide conflicting values for the same asset, signal, and timestamp, the system must never silently average, select latest, or drop one. It must route to human review.
- **AGENTS.md Rule 5 (Full Provenance):** Every measurement in the assembled batch must retain its cell coordinate, sheet name, and source file.
- **ADR-005 (Partial-Batch Policy):** In a mixed batch where some files pass validation and others contain defects, the system must support `PUBLISH_ACCEPTED_FLAG_REVIEW` (Option a) — publishing the accepted subset with full warnings while holding back defective files.

## Decision
1. **Multi-File Columnar Union:**
   - Per-file PyArrow measurement tables and provenance maps are concatenated using `pa.concat_tables()` without copying or mutating underlying buffers.
   - Schemas are strictly validated for alignment across all admitted files.
2. **Asset Roster Completeness Audit:**
   - The `BatchReconciler` compares all assets discovered across accepted files against `contract.expected_assets`.
   - Any missing asset triggers `ERR_VAL_MISSING_ASSET`, records the missing asset identifier in `BatchValidationReport.files_missing`, and sets overall batch status to `REVIEW_REQUIRED`.
3. **Cross-File Telemetry Conflict Detection:**
   - Observations are uniquely identified by `(asset_id, signal_id, timestamp_utc)`.
   - If multiple files emit conflicting values for the same coordinate tuple, `ERR_VAL_CROSS_FILE_DISAGREEMENT` is flagged.
   - Zero silent deduplication or heuristic averaging is permitted.
4. **Policy Enforcement via BatchAssembler:**
   - Under `PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW`: Accepted files are assembled into `batch_measurements_table` and `batch_provenance_table`. Defective files are omitted from the tables and packaged into the review queue. The batch verdict remains `REVIEW_REQUIRED` until a steward clears all items.
   - Under `PartialBatchPolicy.ALL_OR_NOTHING`: The presence of any unaccepted file or missing asset suppresses table generation completely.

## Consequences
- Clean, deterministic multi-file datasets with verifiable provenance.
- Immediate interception of missing equipment data or conflicting sensor feeds.
- Safe partial publication supporting operational monitoring while preventing unverified model training.
