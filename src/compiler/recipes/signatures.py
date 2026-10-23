"""Structural signature generation, hashing, and drift detection.

Signatures capture layout topology while strictly excluding volatile cell values
(such as dates, times, readings, or row counts).
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.compiler.contracts.recipes import StructuralSignature
from src.compiler.contracts.structure import WorkbookStructure
from src.compiler.structure.types import DiscoveredLayout


class DriftType(StrEnum):
    """Categorized structural drift types."""

    NONE = "none"
    SHEET_MISMATCH = "sheet_mismatch"
    HEADER_DRIFT = "header_drift"
    MERGE_DRIFT = "merge_drift"
    COLUMN_COUNT_DRIFT = "column_count_drift"


class DriftReport(BaseModel):
    """Report detailing detected structural deviations between baseline and candidate signatures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    has_drift: bool = Field(..., description="True if any structural deviation was detected.")
    drift_type: DriftType = Field(..., description="Primary drift classification.")
    details: list[str] = Field(default_factory=list, description="Specific drift findings.")
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Jaccard similarity over structural elements (1.0 = identical).",
    )


def compute_signature_hash(signature: StructuralSignature) -> str:
    """Compute deterministic SHA-256 hash of a structural signature.

    Volatile data is strictly excluded; hash is computed over canonical JSON
    of sheet names, header patterns, merge coordinates, and min_columns.
    """
    canonical_dict = {
        "sheet_names": list(signature.sheet_names),
        "header_patterns": list(signature.header_patterns),
        "merge_fingerprint": sorted(signature.merge_fingerprint),
        "min_columns": signature.min_columns,
    }
    encoded = json.dumps(canonical_dict, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SignatureGenerator:
    """Generates StructuralSignature from workbook structures or discovered layouts."""

    @staticmethod
    def from_workbook_structure(
        workbook: WorkbookStructure,
        header_patterns: list[str] | None = None,
    ) -> StructuralSignature:
        """Construct signature from a WorkbookStructure, excluding volatile values."""
        sheet_names = [s.name for s in workbook.sheets]

        # Aggregate merge fingerprints across all sheets
        merge_fingerprints: list[str] = []
        for s in workbook.sheets:
            for m in s.merged_ranges:
                merge_fingerprints.append(f"{s.name}!{m}")

        headers: list[str] = header_patterns or []
        min_cols = max((s.max_col for s in workbook.sheets), default=1)

        return StructuralSignature(
            sheet_names=sheet_names,
            header_patterns=headers,
            merge_fingerprint=sorted(merge_fingerprints),
            min_columns=max(1, min_cols),
        )

    @staticmethod
    def from_layout(
        layout: DiscoveredLayout,
        all_sheet_names: list[str] | None = None,
        merge_ranges: list[str] | None = None,
    ) -> StructuralSignature:
        """Construct signature from a single DiscoveredLayout."""
        sheet_names = all_sheet_names or [layout.sheet_name]

        # Extract hierarchical or flat column paths from tables
        header_patterns: list[str] = []
        for table in layout.tables:
            for col in table.columns:
                header_patterns.append(col.path)

        min_cols = len(header_patterns) if header_patterns else 1
        merges = sorted(merge_ranges or [])

        return StructuralSignature(
            sheet_names=sheet_names,
            header_patterns=header_patterns,
            merge_fingerprint=merges,
            min_columns=max(1, min_cols),
        )

    @staticmethod
    def create(
        sheet_names: list[str],
        header_patterns: list[str],
        merge_fingerprint: list[str] | None = None,
        min_columns: int | None = None,
    ) -> StructuralSignature:
        """Direct constructor for signature with normalized fields."""
        min_cols = min_columns if min_columns is not None else max(1, len(header_patterns))
        return StructuralSignature(
            sheet_names=list(sheet_names),
            header_patterns=list(header_patterns),
            merge_fingerprint=sorted(merge_fingerprint or []),
            min_columns=max(1, min_cols),
        )


class DriftDetector:
    """Detects structural drift between a baseline signature and a candidate workbook signature."""

    @staticmethod
    def detect(baseline: StructuralSignature, candidate: StructuralSignature) -> DriftReport:
        """Compare candidate against baseline, identifying any structural deviations."""
        details: list[str] = []
        primary_drift = DriftType.NONE

        # 1. Sheet name comparison
        baseline_sheets = set(baseline.sheet_names)
        candidate_sheets = set(candidate.sheet_names)
        missing_sheets = baseline_sheets - candidate_sheets
        extra_sheets = candidate_sheets - baseline_sheets

        if missing_sheets or extra_sheets:
            primary_drift = DriftType.SHEET_MISMATCH
            if missing_sheets:
                details.append(f"Missing required sheets: {sorted(missing_sheets)}")
            if extra_sheets:
                details.append(f"Unexpected additional sheets: {sorted(extra_sheets)}")

        # 2. Header pattern comparison
        baseline_headers = list(baseline.header_patterns)
        candidate_headers = list(candidate.header_patterns)
        if baseline_headers != candidate_headers:
            if primary_drift == DriftType.NONE:
                primary_drift = DriftType.HEADER_DRIFT
            missing_headers = set(baseline_headers) - set(candidate_headers)
            added_headers = set(candidate_headers) - set(baseline_headers)
            if missing_headers:
                details.append(f"Missing expected headers: {sorted(missing_headers)}")
            if added_headers:
                details.append(f"New unrecognized headers: {sorted(added_headers)}")
            if not missing_headers and not added_headers:
                details.append("Header order or structure has shifted.")

        # 3. Merge fingerprint comparison
        baseline_merges = set(baseline.merge_fingerprint)
        candidate_merges = set(candidate.merge_fingerprint)
        if baseline_merges != candidate_merges:
            if primary_drift == DriftType.NONE:
                primary_drift = DriftType.MERGE_DRIFT
            missing_merges = baseline_merges - candidate_merges
            added_merges = candidate_merges - baseline_merges
            if missing_merges:
                details.append(f"Missing merge regions: {sorted(missing_merges)}")
            if added_merges:
                details.append(f"Altered/added merge regions: {sorted(added_merges)}")

        # 4. Column count comparison
        if candidate.min_columns < baseline.min_columns:
            if primary_drift == DriftType.NONE:
                primary_drift = DriftType.COLUMN_COUNT_DRIFT
            details.append(
                f"Candidate columns ({candidate.min_columns}) below baseline "
                f"minimum ({baseline.min_columns})"
            )

        # 5. Compute similarity score (Jaccard similarity across elements)
        baseline_elements = (
            set(baseline.sheet_names) | set(baseline.header_patterns) | baseline_merges
        )
        candidate_elements = (
            set(candidate.sheet_names) | set(candidate.header_patterns) | candidate_merges
        )

        if not baseline_elements and not candidate_elements:
            similarity = 1.0
        else:
            intersection = len(baseline_elements & candidate_elements)
            union = len(baseline_elements | candidate_elements)
            similarity = round(intersection / union, 4) if union > 0 else 1.0

        has_drift = len(details) > 0 or primary_drift != DriftType.NONE

        return DriftReport(
            has_drift=has_drift,
            drift_type=primary_drift,
            details=details,
            similarity_score=similarity,
        )
