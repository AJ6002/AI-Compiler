# ADR-012: Recipe Signatures, Drift Detection, and Review Queue

## Status
Accepted

## Context
As recurring workbooks arrive from identical client generation systems (e.g. SCADA historians, automated lab exporters), re-running discovery and ambiguity scoring for every identical file is redundant. However, blindly applying previously approved extraction plans without verification creates severe data corruption risks when spreadsheet layouts drift (e.g. new columns inserted, header paths altered, merged ranges changed, or unexpected sheets introduced).

Furthermore:
- **AGENTS.md Rule 3 (Zero Speculative Manipulation):** Workbooks must not be silently forced into stale recipes without explicit drift validation.
- **AGENTS.md Rule 6 (No Confidence-Based Acceptance):** Ambiguities or structural deviations must be held back in a human review queue with clear audit tracking.
- **Multi-Tenant Isolation:** Client recipes must not leak cross-tenant unless explicitly approved as universal templates.

## Decision
1. **Volatile Content Exclusion in Signatures:**
   - `StructuralSignature` captures purely topological features: ordered worksheet names, hierarchical header strings, sorted merge fingerprints (`Sheet!A1:B1`), and minimum column count.
   - All volatile data (cell values, timestamps, dates, row counts, filename variants) is strictly excluded, ensuring two workbooks with identical structure but different data rows produce the identical deterministic SHA-256 signature hash.
2. **Deterministic Drift Detection:**
   - The `DriftDetector` evaluates incoming signatures against baseline recipes across 4 dimensions: sheet names, header paths, merge fingerprints, and column counts.
   - Any detected deviation triggers `has_drift=True`, classifies the specific `DriftType` (`SHEET_MISMATCH`, `HEADER_DRIFT`, `MERGE_DRIFT`, `COLUMN_COUNT_DRIFT`), and computes Jaccard structural similarity. Drifted files are never replayed automatically.
3. **Tenant-Scoped Recipe Registry:**
   - `RecipeRegistry` enforces strict tenant isolation by default (`SharingTier.TENANT_BOUND`). Tenant B cannot access Tenant A's recipes.
   - `SharingTier.TEMPLATE` recipes can only be matched when callers explicitly allow templates (`allow_templates=True`).
   - Revocation is cryptographically tracked: revoking a recipe marks `is_revoked=True` and permanently suppresses candidate matching.
4. **Data Steward Review Queue with 24-Hour SLA:**
   - Files rejected by discovery or validation gates are packaged into immutable `ReviewItem` records containing the draft plan, discovered headers, validation errors, and reconciliation summaries.
   - `sla_target_at` is automatically computed at `created_at + 24 hours` to enforce operational turnaround SLAs.
   - Approval workflow: Data stewards can inspect, approve, or correct draft plans, promoting them into versioned, immutable `Recipe` records in the registry.

## Consequences
- Fast-path replay of high-frequency recurring workbooks without sacrificing structural verification.
- Zero silent schema drift: altered client spreadsheets immediately route to human review.
- Strict tenant data boundaries are preserved across all recipe lookups.
