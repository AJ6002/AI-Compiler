# Excel Workbook Exploration Workbench

Local read-only CLI tool for data stewards and developers to inspect untrusted Excel workbooks before drafting or promoting parsing recipes.

## Purpose

As specified in Phase 0 (G7) of the AICONNEX Industrial Excel Compiler Build Plan:
- Opens an Excel file in read-only mode (no network access, no macro execution).
- Analyzes sheet dimensions, merged cell coordinates, candidate header bands, and data regions.
- Identifies duplicate column names across potential header rows.
- Emits a draft recipe JSON schema for human review and promotion.

> [!NOTE]
> This tool runs exclusively on the steward's local machine or container. It is **not** part of the automated deployed ingestion pipeline. Its output is an advisory draft only; all recipes must undergo human review and contract verification before deployment.

---

## Usage

### Local CLI (via `uv`)
```powershell
# Explore a workbook and display human-readable terminal analysis
uv run python tools/exploration/explore.py path/to/workbook.xlsx

# Inspect a specific sheet
uv run python tools/exploration/explore.py path/to/workbook.xlsx --sheet "Sheet1"

# Emit raw JSON summary and draft recipe
uv run python tools/exploration/explore.py path/to/workbook.xlsx --json
```

### Docker Sandbox
You can also run the exploration tool inside an isolated, network-disabled container:
```powershell
docker build -t aiconnex-explore -f tools/exploration/Dockerfile .
docker run --rm --network none -v ${PWD}/data:/data:ro aiconnex-explore /data/sample.xlsx
```
