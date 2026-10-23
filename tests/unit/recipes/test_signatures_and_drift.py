"""Unit tests for StructuralSignature, volatile exclusion, and drift detection."""

from src.compiler.contracts.structure import RegionBoundary, SheetStructure, WorkbookStructure
from src.compiler.recipes.signatures import (
    DriftDetector,
    DriftType,
    SignatureGenerator,
    compute_signature_hash,
)
from src.compiler.structure.types import DiscoveredLayout, HeaderPath, TableRegionLayout


def test_signature_determinism_and_volatile_exclusion():
    """Verify that different volatile values (dates, readings) do not change the signature hash."""
    # Workbook 1: Day 1 readings
    wb1 = WorkbookStructure(
        tenant_id="tenant_a",
        project_id="proj_1",
        source_sha256="abc111",
        workbook_name="compressor_2026_10_01.xlsx",
        sheets=[
            SheetStructure(
                name="Telemetry",
                index=0,
                max_row=500,  # 500 rows on day 1
                max_col=4,
                merged_ranges=["A1:D1"],
            )
        ],
    )
    headers = ["TIMESTAMP", "DISPENSER_1.PRESSURE", "DISPENSER_1.FLOW", "DISPENSER_1.TEMP"]
    sig1 = SignatureGenerator.from_workbook_structure(wb1, header_patterns=headers)
    hash1 = compute_signature_hash(sig1)

    # Workbook 2: Day 2 readings (different row count, different source sha, different file name)
    wb2 = WorkbookStructure(
        tenant_id="tenant_a",
        project_id="proj_1",
        source_sha256="xyz999",
        workbook_name="compressor_2026_10_02.xlsx",
        sheets=[
            SheetStructure(
                name="Telemetry",
                index=0,
                max_row=2800,  # 2800 rows on day 2
                max_col=4,
                merged_ranges=["A1:D1"],
            )
        ],
    )
    sig2 = SignatureGenerator.from_workbook_structure(wb2, header_patterns=headers)
    hash2 = compute_signature_hash(sig2)

    assert hash1 == hash2, (
        "Structural signatures must match when layout is topologically identical."
    )
    assert sig1.sheet_names == ["Telemetry"]
    assert sig1.merge_fingerprint == ["Telemetry!A1:D1"]
    assert sig1.header_patterns == headers


def test_signature_generation_from_discovered_layout():
    """Verify signature creation from Phase 5 DiscoveredLayout."""
    layout = DiscoveredLayout(
        sheet_name="Sensors",
        tables=[
            TableRegionLayout(
                boundary=RegionBoundary(min_row=1, max_row=100, min_col=1, max_col=3),
                header_rows=[1],
                data_start_row=2,
                data_end_row=100,
                columns=[
                    HeaderPath(column_index=1, path="TIME", leaf_name="TIME"),
                    HeaderPath(
                        column_index=2, path="PUMP.RPM", leaf_name="RPM", ancestors=["PUMP"]
                    ),
                    HeaderPath(
                        column_index=3, path="PUMP.VIB", leaf_name="VIB", ancestors=["PUMP"]
                    ),
                ],
            )
        ],
    )

    sig = SignatureGenerator.from_layout(layout, merge_ranges=["A1:C1"])
    assert sig.sheet_names == ["Sensors"]
    assert sig.header_patterns == ["TIME", "PUMP.RPM", "PUMP.VIB"]
    assert sig.merge_fingerprint == ["A1:C1"]
    assert sig.min_columns == 3


def test_drift_detection_no_drift():
    """Identical signatures must report no drift and 1.0 similarity."""
    sig_a = SignatureGenerator.create(
        sheet_names=["Sheet1"],
        header_patterns=["A", "B", "C"],
        merge_fingerprint=["A1:B1"],
    )
    sig_b = SignatureGenerator.create(
        sheet_names=["Sheet1"],
        header_patterns=["A", "B", "C"],
        merge_fingerprint=["A1:B1"],
    )

    report = DriftDetector.detect(sig_a, sig_b)
    assert not report.has_drift
    assert report.drift_type == DriftType.NONE
    assert report.similarity_score == 1.0
    assert len(report.details) == 0


def test_drift_detection_sheet_mismatch():
    """Missing or added sheets must be flagged as SHEET_MISMATCH."""
    baseline = SignatureGenerator.create(
        sheet_names=["Telemetry", "Diagnostics"],
        header_patterns=["TIME", "VAL"],
    )
    # Candidate missing 'Diagnostics' sheet
    candidate = SignatureGenerator.create(
        sheet_names=["Telemetry"],
        header_patterns=["TIME", "VAL"],
    )

    report = DriftDetector.detect(baseline, candidate)
    assert report.has_drift
    assert report.drift_type == DriftType.SHEET_MISMATCH
    assert any("Missing required sheets" in d for d in report.details)
    assert report.similarity_score < 1.0


def test_drift_detection_header_drift():
    """Modified header paths must be detected as HEADER_DRIFT."""
    baseline = SignatureGenerator.create(
        sheet_names=["Data"],
        header_patterns=["TIMESTAMP", "PRESS", "TEMP"],
    )
    # Candidate has extra column 'FLOW' and altered 'TEMP' to 'TEMPERATURE'
    candidate = SignatureGenerator.create(
        sheet_names=["Data"],
        header_patterns=["TIMESTAMP", "PRESS", "TEMPERATURE", "FLOW"],
    )

    report = DriftDetector.detect(baseline, candidate)
    assert report.has_drift
    assert report.drift_type == DriftType.HEADER_DRIFT
    assert any("Missing expected headers" in d for d in report.details)
    assert any("New unrecognized headers" in d for d in report.details)


def test_drift_detection_merge_drift():
    """Altered merged coordinate ranges must be flagged as MERGE_DRIFT."""
    baseline = SignatureGenerator.create(
        sheet_names=["Data"],
        header_patterns=["A", "B", "C"],
        merge_fingerprint=["A1:B1"],
    )
    candidate = SignatureGenerator.create(
        sheet_names=["Data"],
        header_patterns=["A", "B", "C"],
        merge_fingerprint=["A1:C1"],  # merge expanded across 3 columns
    )

    report = DriftDetector.detect(baseline, candidate)
    assert report.has_drift
    assert report.drift_type == DriftType.MERGE_DRIFT
    assert any("Missing merge regions" in d for d in report.details)
    assert any("Altered/added merge regions" in d for d in report.details)


def test_drift_detection_column_count_drift():
    """Candidate with fewer columns than baseline minimum must be flagged."""
    baseline = SignatureGenerator.create(
        sheet_names=["Data"],
        header_patterns=["A", "B", "C", "D"],
        min_columns=4,
    )
    candidate = SignatureGenerator.create(
        sheet_names=["Data"],
        header_patterns=["A", "B", "C", "D"],
        min_columns=2,  # Truncated
    )

    report = DriftDetector.detect(baseline, candidate)
    assert report.has_drift
    assert report.drift_type == DriftType.COLUMN_COUNT_DRIFT
