# ADR-005: Partial-Batch Publication Policy

## Status
Accepted

## Context
Industrial spreadsheet uploads frequently arrive as multi-file ZIP archives (e.g. 20 compressor logs). In real-world client data, a batch often contains 18 valid files and 2 defective or ambiguous files (e.g., corrupted time column, unmapped serial). A clear publication policy is required to prevent blocking valid operational data while preventing defective data from entering automated training pipelines.

## Decision
Adopt **Option (a): Publish accepted files while setting batch status to `REVIEW_REQUIRED`**.
1. **Per-File Processing:** Each file is evaluated independently against its structural signature and client contract.
2. **Batch Manifest Tracking:** The batch manifest records `assets_expected`, `assets_accepted`, and `assets_missing_coverage` with explicit per-file statuses.
3. **Downstream Gating:** Downstream AutoMLOps consumers ingest published accepted files only when permitted by tenant pipeline policy, but the overall batch remains flagged as `REVIEW_REQUIRED` until human reviewers clear the defective files.
4. **Idempotent Follow-Up:** When a reviewer approves a recipe or corrects an unmapped asset for the held-back files, an incremental patch is published without re-parsing already-accepted files.

## Consequences
- Operations are not halted by a single corrupted sheet in a large archive.
- Defective data is completely isolated and prevented from auto-consumption.
