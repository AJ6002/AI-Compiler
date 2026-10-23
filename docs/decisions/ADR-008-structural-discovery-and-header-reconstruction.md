# ADR-008: Structural Discovery and Hierarchical Header Reconstruction

## Status
Accepted

## Context
Industrial spreadsheets contain wildly disparate layouts: single flat tables, multi-row merged header bands with duplicate leaf column names (e.g., duplicate `PRESSURE` under different compressor stages or dispensers), and scattered tables preceded by key-value metadata blocks.

Hardcoding row or column indices fails immediately when client templates evolve, when rows are added, or when exports are reformatted. Conversely, relying on probabilistic LLM table guessing violates AGENTS.md Rule 3 (Zero Speculative Manipulation) and Rule 6 (No Confidence-Based Acceptance).

## Decision
1. **Occupancy & Type Matrix (`OccupancyGrid`):**
   - Eliminate hardcoded row/column assumptions by constructing a 2D occupancy and cell signature matrix (`z`, `s`, `n`, `d`, `duration`, `f`, `b`, `e`).
   - Identify table regions via density transitions and blank separator boundaries.
2. **Metadata Block Isolation:**
   - Detect isolated sparse rows (e.g. `Facility: Station 4`) as `metadata_block` regions.
   - Extract key-value pairs without polluting measurement table column definitions.
3. **Hierarchical Header Reconstruction:**
   - Multi-row header bands propagate merged parent group labels down through child columns.
   - Column paths are reconstructed as dot-separated hierarchies (e.g. `DISPENSER_1.HOSE_A.PRESSURE`).
   - Sibling columns with identical leaf labels (`PRESSURE`) are disambiguated by ancestor context.
4. **Strict Ambiguity Routing (`AmbiguityScorer`):**
   - Unresolved duplicate paths, overlapping regions, or empty data segments emit diagnostic error codes (`ERR_STRUCT_DUPLICATE_COLUMNS`, `ERR_STRUCT_AMBIGUOUS_HEADER`, `ERR_STRUCT_DISPERSED_REGIONS`).
   - Structural ambiguity routes unconditionally to `JobResultState.REVIEW_REQUIRED`.
5. **Pluggable Discovery Interface (`StructuralDiscoveryEngine`):**
   - Define a decoupled engine protocol implemented by `RuleBasedDiscoveryEngine`.
   - Wrap optional ML discovery models (such as GridGulp) in `GridGulpAdapter` behind the identical protocol with deterministic fallback.

## Consequences
- Single-pass and batch workflows can automatically extract complex tables without hardcoding layout coordinates.
- Duplicate column names are deterministically resolved into qualified ancestor paths.
- Indeterminate or conflicting layouts are caught early and routed to human steward review.
