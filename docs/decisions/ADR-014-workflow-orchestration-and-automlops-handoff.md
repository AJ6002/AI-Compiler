# ADR-014: Workflow Orchestration, Review Wait-States, and AutoMLOps Handoff

## Status
Accepted

## Context
Industrial spreadsheets are uploaded in batches through client portals, SCADA automations, or data engineering teams. Ingesting these files requires durable workflow coordination that survives network interruptions, worker restarts, and long-lived human review loops without corrupting data or triggering retry storms.

Furthermore:
- **AGENTS.md Rule 6 (No Confidence-Based Acceptance):** No dataset may be published to automated training based on model speculation. Outstanding defects must pause the workflow in a human review wait-state.
- **AGENTS.md Rule 7 (Architectural Discipline):** Orchestration must function deterministically in lightweight local environments (in-process durable execution) while presenting identical activity boundaries for Temporal deployment.
- **Idempotent Outbox Delivery:** Downstream AutoMLOps consumers require cryptographic verification of datasets before training ingestion.

## Decision
1. **FastAPI Control Plane (`/api/v1/jobs`):**
   - Endpoints expose job creation, upload-triggered execution, status polling, review wait-state decision signals, artifact catalogs, and file downloads.
   - Strict tenant and project authorization (`X-Tenant-ID`, `X-Project-ID`) on every lookup prevents cross-tenant data leaks.
2. **Deterministic Activity Boundaries:**
   - The workflow pipeline is partitioned into 6 deterministic activities: Admission, Discovery, Recipe Resolution, Execution, Validation, and Batch Reconciliation & Publication.
   - Faults are classified into `InfrastructureFault` (exponential backoff) vs `DeterministicSourceFault` (fail-fast without retry storms).
3. **Dual Workflow Engine Architecture:**
   - An in-process `DurableWorkflowEngine` maintains persistent `JobRecord` states, manages activity execution, pauses on `JobStatus.REVIEW_REQUIRED`, and resumes upon steward signals.
   - Shares exact activity interfaces with Temporal Python SDK.
4. **Staging vs Publication Isolation:**
   - Working files are generated under `staging/{job_id}/...`. Atomic commit occurs only when moving tables to `published/{dataset_id}/...` and writing `manifest.json` and `handoff.json`.
5. **AutoMLOps Handoff Outbox:**
   - Emits `HandoffEvent` records with SHA-256 idempotency deduplication. Downstream AutoMLOps consumers enforce hard validation gates, blocking unverified or incomplete datasets from automated model training.

## Consequences
- Guaranteed state recovery without lost jobs or duplicate published datasets.
- Clean separation of concerns between HTTP control plane, durable orchestration, and downstream model pipelines.
