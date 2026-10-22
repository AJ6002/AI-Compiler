# ADR-004: Frozen Contracts and Observation Identity

## Status
Accepted

## Context
Downstream AutoMLOps consumers and automated data transformation pipelines require immutable, strongly-typed contracts. Without explicit observation identity, spreadsheets containing multiple readings at the same timestamp (or missing timestamps) suffer from accidental deduplication, row collision, or silent truncation.

## Decision
1. **Pydantic v2 Frozen Contracts:** All compiler contracts inherit from `BaseContract` enforcing `extra="forbid"`, `frozen=True`, and `schema_version="1.0.0"`.
2. **Observation Identity Definition:** One observation is strictly defined as `(asset_id, timestamp_utc, raw_source_row)`. A deterministic SHA-256 hash is computed across this tuple to provide an immutable identity (`observation_id`). All signals extracted from that row share this observation ID.
3. **Execution vs Result Separation:** Workflow state (`JobExecutionState`) tracks activity progress (RECEIVED -> INSPECTING -> PLANNING -> EXECUTING -> VALIDATING -> COMPLETED), whereas quality verdict (`JobResultState`) tracks publication eligibility (ACCEPTED, REVIEW_REQUIRED, UNSUPPORTED, FAILED).

## Consequences
- Downstream models preserve event-level fidelity without synthetic row grouping.
- Contract serialization errors surface immediately at the admission or plan validation stage.
