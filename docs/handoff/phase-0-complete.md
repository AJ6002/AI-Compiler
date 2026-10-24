# Phase 0 Completion Note: Clean the Substrate

**Date:** 2026-10-25  
**Status:** COMPLETE (All 4 Tasks Implemented & Verified)  
**Governing Standard:** `AGENTS.md` & `RULE[user_global]`  

---

## 1. Summary of Changes

Phase 0 resolves two foundational defects in the deterministic compilation substrate before launching sandbox investigation agents:
1. **Timestamp Resolution Fix:** Eliminated the token collision bug in `PlanExecutor._resolve_timestamp()` that forced `"DATE & TIME"` combined columns to epoch fallback `1970-01-01`.
2. **Dual-Engine Reader (python-calamine):** Integrated Rust-backed `python-calamine` into `pyproject.toml`, implemented `CalamineReader` adhering to `ExcelReader` protocol, and exposed `get_reader()` factory.
3. **Dry-Run Mode:** Added `dry_run: bool = False` to `PlanExecutor.execute()` ensuring zero side-effects on persistent storage during validation dry-runs.
4. **ADR-007 Recorded:** Updated `docs/decisions/ADR-007-openpyxl-dual-pass-and-formula-cache-isolation.md` to `ACCEPTED — IMPLEMENTED (Dual-Engine Calamine + Openpyxl)`.

---

## 2. Files Changed and Created

### Source Code:
- `pyproject.toml` — Added `"python-calamine>=0.3.0"` to dependencies.
- `src/compiler/readers/calamine_reader.py` — *[NEW]* High-throughput reader wrapping `python-calamine` with `probe()`, `inspect()`, and `extract_sheet_cells()`.
- `src/compiler/readers/__init__.py` — Exported `CalamineReader` and `get_reader()` factory.
- `src/compiler/execution/executor.py` — Updated `_resolve_timestamp()` to support combined date/time columns; updated `__init__` to use `get_reader()`; added `dry_run` parameter to `execute()`.

### Documentation:
- `docs/decisions/ADR-007-openpyxl-dual-pass-and-formula-cache-isolation.md` — Updated status and dual-engine architecture specification.

### Tests:
- `tests/unit/execution/test_executor_timestamp.py` — *[NEW]* Verifies single `"DATE & TIME"` column resolves real UTC timestamp (`2025-11-04 10:30:00`), not epoch.
- `tests/unit/execution/test_executor_dry_run.py` — *[NEW]* Verifies `dry_run=True` returns complete tables without external storage mutations.
- `tests/unit/readers/test_calamine_reader.py` — *[NEW]* Validates 100% cell coordinate and data type parity against `OpenpyxlReader` on `simple_table_ltds.xlsx`, and verifies Calamine speed advantage (< 0.5x ratio on 10k rows).

---

## 3. Verification Commands Run & Results

| Command | Result | Notes |
|---|---|---|
| `uv sync --all-extras` | SUCCESS | Installed `python-calamine 0.9.0` and dev dependencies. |
| `uv run pytest -q` | **118 passed** | 114 baseline + 4 new tests. Zero regressions. |
| `uv run ruff check .` | **0 errors, 0 warnings** | Full lint compliance. |
| `uv run pytest tests/unit/execution/test_executor_timestamp.py -v` | **PASSED** | Timestamp resolves to 2025-11-04T10:30:00+00:00. |
| `uv run pytest tests/unit/execution/test_executor_dry_run.py -v` | **PASSED** | Dry-run produces tables without storage mutations. |
| `uv run pytest tests/unit/readers/test_calamine_reader.py -v` | **PASSED** | 100% parity across 459 cells; 10k row speed ratio = 0.204 (< 0.50). |

---

## 4. Benchmark Numbers: Before vs. After (Suyash Dataset: `suyash2.zip`)

Archive: 4 SCADA workbooks, 26,930 rows, 1,720,448 measurement cells + 1,720,448 provenance cells.

| Metric | Baseline (Openpyxl-Only) | Phase 0 (Calamine Dual-Engine) | Improvement |
|---|---|---|---|
| **Reader Inspection Time (4 files)** | ~27.0s | **1.36s** | **~20x faster** |
| **Executor Compilation Time (4 files)** | ~34.5s | **30.89s** | **~10% faster** |
| **End-to-End Pipeline Wall-Clock** | **62.80s** | **42.19s** | **32.8% reduction** |
| **10,000-row Synthetic Extraction** | 0.956s | **0.195s** | **4.9x faster (ratio: 0.204)** |
| **Numerical & Provenance Fidelity** | 100.0% | **100.0%** | Zero drift |

---

## 5. Surprises & Key Observations

1. **Rust-backed Speed on File Inspection:** Calamine's `inspect()` dropped per-file metadata and preview parsing from **7.63s down to 0.17s–0.45s**.
2. **Zero Ingestion Parity Discrepancy:** On `simple_table_ltds.xlsx`, all 459 extracted cells produced identical string, numeric, and date types between `OpenpyxlReader` and `CalamineReader` with zero mapping discrepancies.
3. **Clean Timestamp Normalization:** The combined date-time resolver easily parses ISO-8601 strings and native Excel date objects without needing separate splitting or regex heuristics.
