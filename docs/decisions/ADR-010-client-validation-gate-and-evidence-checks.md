# ADR-010: Client Validation Gate and Evidence-Based Acceptance

## Status
Accepted

## Context
Downstream machine learning pipelines (AutoMLOps) and operational dashboards depend on high-integrity telemetry datasets. Publishing datasets with dropped signals, conflicting timestamps, unauthorized engineering units, or unverified asset tags causes silent prediction errors or training corruption.

Per AGENTS.md:
- Rule 6 (No Confidence-Based Acceptance): Model confidence or heuristic likelihood must never be the sole basis for dataset publication.
- Rule 9 (Strict Phase Boundaries): Datasets that fail any contract requirement must immediately route to `REVIEW_REQUIRED` with clear evidence references.

## Decision
1. **ClientValidationGate as Final Pre-Publication Boundary:**
   - No dataset is published or flagged as `ACCEPTED` without passing `ClientValidationGate.validate()`.
2. **Four Specialized Validation Pillars:**
   - **Signal & Unit Validation:** Enforces presence of all `required_signals`. Validates metadata and column units against `allowed_units` (`ERR_VAL_MISSING_SIGNAL`, `ERR_VAL_UNRESOLVED_UNIT`).
   - **Temporal & Cadence Validation:** Verifies UTC normalization. Checks sampling interval stability ($\Delta t$) against `expected_cadence_seconds` (`ERR_VAL_CADENCE_IRREGULAR`, `ERR_VAL_TIMEZONE_AMBIGUOUS`).
   - **Asset Roster Validation:** Matches extracted asset tags against `contract.expected_assets` (`ERR_VAL_MISSING_ASSET`).
   - **Reconciliation & Cardinality Validation:** Verifies `actual_emitted_records == expected_emitted_records` to detect and block Cartesian row multiplication (`ERR_EXEC_ROW_MULTIPLICATION`).
3. **Structured Diagnostic Records:**
   - Every issue emits a [`ValidationErrorItem`](file:///x:/data-compiler/src/compiler/contracts/validation.py#L11) with error code, severity, human-readable message, affected cell coordinate, signal path, and actionable remediation text for data stewards.
4. **Deterministic Gate Verdict:**
   - Any single `FATAL` or `ERROR` issue forces `result_state = JobResultState.REVIEW_REQUIRED`.
   - Datasets achieve `JobResultState.ACCEPTED` strictly when all blocking errors are absent.

## Consequences
- Untrusted, ambiguous, or damaged files are blocked before downstream consumption.
- Data stewards receive exact coordinates and guidance needed to resolve anomalies.
