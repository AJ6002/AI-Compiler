"""Formula inspection and cache isolation utilities.

Per AGENTS.md Rules 1 & 4 (Untrusted Data Boundary & Execution Safety):
Uploaded spreadsheet contents must NEVER be evaluated, executed, or interpreted
as executable python code.

Formulas are inspected structurally to:
1. Preserve formula expressions and cached evaluations as separate fields.
2. Flag missing or stale formula caches (common in third-party or pandas-generated workbooks).
3. Detect external workbook dependencies (e.g. '[OtherFile.xlsx]Sheet1'!A1).
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Matches external workbook references enclosed in square brackets:
# e.g., '[Budget2025.xlsx]Sheet1'!$A$1 or '[1]Sheet1'!A1
EXTERNAL_REF_REGEX = re.compile(r"\[([^\]]+)\]")


class FormulaInspection(BaseModel):
    """Structural analysis of a potential formula cell."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    has_formula: bool = Field(default=False, description="True if cell contains a formula.")
    formula_text: str | None = Field(
        default=None, description="Raw formula string (starts with =)."
    )
    cached_value: Any = Field(default=None, description="Cached evaluated value from Excel cache.")
    is_cache_missing: bool = Field(
        default=False,
        description="True if cell has a formula but no valid cached value.",
    )
    has_external_reference: bool = Field(
        default=False,
        description="True if formula depends on an external workbook.",
    )
    external_targets: list[str] = Field(
        default_factory=list,
        description="List of external workbook names/indices referenced in formula.",
    )


def extract_external_references(formula_text: str) -> list[str]:
    """Extract referenced external workbook identifiers from formula text."""
    if not formula_text or not formula_text.startswith("="):
        return []
    matches = EXTERNAL_REF_REGEX.findall(formula_text)
    # Deduplicate while preserving order
    seen: set[str] = set()
    targets: list[str] = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            targets.append(match)
    return targets


def inspect_formula_cell(
    raw_value: Any,
    cached_value: Any = None,
) -> FormulaInspection:
    """Analyze a cell value for formula syntax and cached evaluation status.

    Parameters
    ----------
    raw_value:
        Cell value loaded with data_only=False (contains '=...' if formula).
    cached_value:
        Cell value loaded with data_only=True (contains evaluated result if cached).
    """
    if isinstance(raw_value, str) and raw_value.startswith("="):
        formula_str = raw_value.strip()
        external_refs = extract_external_references(formula_str)

        # Cache is missing if cached_value is None or still equals formula text
        cache_missing = cached_value is None or (
            isinstance(cached_value, str) and cached_value.startswith("=")
        )

        return FormulaInspection(
            has_formula=True,
            formula_text=formula_str,
            cached_value=None if cache_missing else cached_value,
            is_cache_missing=cache_missing,
            has_external_reference=len(external_refs) > 0,
            external_targets=external_refs,
        )

    # Not a formula cell
    return FormulaInspection(
        has_formula=False,
        formula_text=None,
        cached_value=None,
        is_cache_missing=False,
        has_external_reference=False,
        external_targets=[],
    )
