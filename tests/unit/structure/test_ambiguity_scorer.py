"""Unit tests for AmbiguityScorer and REVIEW_REQUIRED routing."""

from src.compiler.contracts.enums import ErrorCode, JobResultState
from src.compiler.contracts.structure import RegionBoundary
from src.compiler.structure.ambiguity_scorer import AmbiguityScorer
from src.compiler.structure.types import HeaderPath, TableRegionLayout


def test_scorer_accepted_on_clean_table() -> None:
    scorer = AmbiguityScorer()
    columns = [
        HeaderPath(column_index=1, path="TIMESTAMP", leaf_name="TIMESTAMP"),
        HeaderPath(column_index=2, path="PRESSURE", leaf_name="PRESSURE"),
    ]
    table = TableRegionLayout(
        boundary=RegionBoundary(min_row=1, max_row=20, min_col=1, max_col=2, region_type="table"),
        header_rows=[1],
        data_start_row=2,
        data_end_row=20,
        columns=columns,
    )

    verdict, errors, _ = scorer.evaluate_layout(tables=[table], unassigned_regions=[])
    assert verdict == JobResultState.ACCEPTED
    assert errors == []


def test_scorer_catches_duplicate_columns() -> None:
    scorer = AmbiguityScorer()
    # Two columns with identical reconstructed path "PRESSURE"
    columns = [
        HeaderPath(column_index=1, path="TIMESTAMP", leaf_name="TIMESTAMP"),
        HeaderPath(column_index=2, path="PRESSURE", leaf_name="PRESSURE"),
        HeaderPath(column_index=3, path="PRESSURE", leaf_name="PRESSURE"),
    ]
    table = TableRegionLayout(
        boundary=RegionBoundary(min_row=1, max_row=20, min_col=1, max_col=3, region_type="table"),
        header_rows=[1],
        data_start_row=2,
        data_end_row=20,
        columns=columns,
    )

    verdict, errors, diagnostics = scorer.evaluate_layout(tables=[table], unassigned_regions=[])
    assert verdict == JobResultState.REVIEW_REQUIRED
    assert ErrorCode.ERR_STRUCT_DUPLICATE_COLUMNS in errors
    assert any("duplicate unresolved column headers" in d for d in diagnostics)


def test_scorer_catches_unassigned_dispersed_regions() -> None:
    scorer = AmbiguityScorer()
    columns = [
        HeaderPath(column_index=1, path="TIMESTAMP", leaf_name="TIMESTAMP"),
    ]
    table = TableRegionLayout(
        boundary=RegionBoundary(min_row=1, max_row=10, min_col=1, max_col=1, region_type="table"),
        header_rows=[1],
        data_start_row=2,
        data_end_row=10,
        columns=columns,
    )
    unassigned = [RegionBoundary(min_row=15, max_row=20, min_col=5, max_col=6, region_type="table")]

    verdict, errors, _ = scorer.evaluate_layout(tables=[table], unassigned_regions=unassigned)
    assert verdict == JobResultState.REVIEW_REQUIRED
    assert ErrorCode.ERR_STRUCT_DISPERSED_REGIONS in errors


def test_scorer_catches_empty_data_region() -> None:
    scorer = AmbiguityScorer()
    columns = [
        HeaderPath(column_index=1, path="TIMESTAMP", leaf_name="TIMESTAMP"),
    ]
    # Header at row 1, but max_row is also 1 (data_start_row 2 > data_end_row 1)
    table = TableRegionLayout(
        boundary=RegionBoundary(min_row=1, max_row=1, min_col=1, max_col=1, region_type="table"),
        header_rows=[1],
        data_start_row=2,
        data_end_row=1,
        columns=columns,
    )

    verdict, errors, diagnostics = scorer.evaluate_layout(tables=[table], unassigned_regions=[])
    assert verdict == JobResultState.REVIEW_REQUIRED
    assert ErrorCode.ERR_STRUCT_AMBIGUOUS_HEADER in errors
    assert any("zero data rows" in d for d in diagnostics)
