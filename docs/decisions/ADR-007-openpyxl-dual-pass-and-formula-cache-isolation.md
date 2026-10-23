# ADR-007: Openpyxl Dual-Pass and Formula Cache Isolation

## Status
Accepted

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
2. **Dual-Pass Extraction:**
   - Coordinate extraction across two openpyxl reader instances: pass 1 (`data_only=False`) extracts raw formula text and merged ranges; pass 2 (`data_only=True`) extracts cached evaluations.
   - Store both `formula` expression and `cached_value` in `CellDetail`.
   - Never evaluate formula strings into python code; strictly inspect syntactic properties.
3. **Cache Missing & External Reference Tracking:**
   - Cells with formula syntax but missing cached values are explicitly identified (`is_cache_missing=True`).
   - Formulas containing external workbook references (`[OtherWorkbook.xlsx]Sheet1!A1`) are extracted and cataloged for review routing.
4. **VBA and Macro Isolation:**
   - `keep_vba=False` is enforced across all openpyxl workbook loading to isolate executable macro streams.
5. **Duration Formatting vs Wall-Clock Timestamps:**
   - Distinguish elapsed duration number formats (`[h]:mm:ss`, `[m]:ss`) from clock dates, parsing duration serials to total elapsed seconds without datetime wrapping errors.

## Consequences
- Readers output deterministic `WorkbookStructure` matching frozen Phase 1 contracts.
- Downstream planner and validators have full visibility into whether a value is a hardcoded literal, a cached formula result, or a missing calculation.
- Memory usage is kept bounded by batching cell extraction and isolating preview sampling.
