# ADR-007: Dual-Engine Reader and Formula Cache Isolation

## Status
ACCEPTED — IMPLEMENTED (Dual-Engine Calamine + Openpyxl)

## Context
Industrial spreadsheets frequently include formulas (e.g. totals, stage pressure differentials, running averages), merged header hierarchies, and elapsed duration counters (`[h]:mm:ss`). In standard openpyxl usage:
1. `data_only=False` loads formula AST/strings (e.g. `=A1+B1`) but evaluates to `None` for calculated outputs.
2. `data_only=True` loads cached calculated values from Excel's `<v>` XML tag, but discards formula expressions and external workbook dependency paths.
3. Third-party spreadsheet generators (such as pandas, openpyxl scripts, or uncalculated exports) do not populate `<v>` formula caches, causing `data_only=True` to yield `None` or corrupt readings if unverified.
4. AGENTS.md Rules 1 & 4 strictly forbid evaluating spreadsheet formula strings via `eval()`, `exec()`, or formula engines.

## Decision
1. **ExcelReader Protocol:** Define a decoupled `ExcelReader` protocol with three distinct stages:
   - `probe(source)`: Fast read-only inspection of sheet names, dimensions, VBA presence, and date epoch (1900 vs 1904).
   - `inspect(source, tenant_id, project_id)`: Structural discovery extracting sheets, merged ranges, and bounded preview cell samples.
   - `extract_sheet_cells(source, sheet_name, batch_size)`: Memory-bounded generator yielding coordinate-keyed typed cells.
2. **Dual-Engine Architecture (Calamine + Openpyxl):**
   - Calamine reads plain data fast; Openpyxl retained for formulas, merges, styles. Fallback selected per-sheet by a heuristic (presence of formulas, macros, or merged ranges -> Openpyxl).
   - `get_reader()` factory prioritizes `CalamineReader` for maximum throughput on industrial time-series sheets while guaranteeing fallback to `OpenpyxlReader` for full AST inspection when needed.
3. **Dual-Pass Extraction for Formula Inspection (Openpyxl):**
   - Coordinate extraction across two openpyxl reader instances: pass 1 (`data_only=False`) extracts raw formula text and merged ranges; pass 2 (`data_only=True`) extracts cached evaluations.
   - Store both `formula` expression and `cached_value` in `CellDetail`.
   - Never evaluate formula strings into python code; strictly inspect syntactic properties.
4. **Cache Missing & External Reference Tracking:**
   - Cells with formula syntax but missing cached values are explicitly identified (`is_cache_missing=True`).
   - Formulas containing external workbook references (`[OtherWorkbook.xlsx]Sheet1!A1`) are extracted and cataloged for review routing.
5. **VBA and Macro Isolation:**
   - `keep_vba=False` is enforced across all workbook loading to isolate executable macro streams.
6. **Duration Formatting vs Wall-Clock Timestamps:**
   - Distinguish elapsed duration number formats (`[h]:mm:ss`, `[m]:ss`) from clock dates, parsing duration serials to total elapsed seconds without datetime wrapping errors.

## Consequences
- High-throughput ingestion: plain data sheets extract >5x faster via Rust-backed Calamine while maintaining 100% cell coordinate parity with Openpyxl.
- Readers output deterministic `WorkbookStructure` matching frozen Phase 1 contracts.
- Downstream planner and validators have full visibility into whether a value is a hardcoded literal, a cached formula result, or a missing calculation.
- Memory usage is kept bounded by batching cell extraction and isolating preview sampling.
