from pathlib import Path

from src.compiler.contracts.enums import ErrorCode, JobResultState
from src.compiler.evaluator import CorpusCatalog, DatasetEvaluator


def get_fixture(fixture_id: str):
    catalog_path = Path("tests/golden/manifests/corpus_catalog.json")
    catalog = CorpusCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    return next(f for f in catalog.fixtures if f.fixture_id == fixture_id)


def test_evaluator_catches_dropped_signal():
    """Verify that evaluator fails if a mandatory signal is missing."""
    fixture = get_fixture("fix_excel_simple_01")
    evaluator = DatasetEvaluator()

    # Records only have SUCTION_PRESS; DISCHARGE_PRESS is dropped
    records = [
        {
            "observation_key": f"obs_{i}",
            "signal_id": "SUCTION_PRESS",
            "value_numeric": 10.0,
            "provenance_id": f"SimpleReadings!A{i}",
        }
        for i in range(1, 51)
    ]

    outcome = evaluator.evaluate(
        actual_result_state=JobResultState.ACCEPTED,
        actual_records=records,
        oracle=fixture,
    )

    assert outcome.passed is False
    assert outcome.signal_coverage_match is False
    assert any("Missing mandatory signals" in f for f in outcome.failures)


def test_evaluator_catches_shifted_row_count():
    """Verify that evaluator fails if rows are dropped or multiplied."""
    fixture = get_fixture("fix_excel_simple_01")
    evaluator = DatasetEvaluator()

    # Truncated records (40 instead of 50)
    records = [
        {
            "observation_key": f"obs_{i}",
            "signal_id": "SUCTION_PRESS",
            "value_numeric": 10.0,
            "provenance_id": f"SimpleReadings!A{i}",
        }
        for i in range(1, 41)
    ]

    outcome = evaluator.evaluate(
        actual_result_state=JobResultState.ACCEPTED,
        actual_records=records,
        oracle=fixture,
    )

    assert outcome.passed is False
    assert outcome.row_count_match is False
    assert any("Row count mismatch" in f for f in outcome.failures)


def test_evaluator_catches_missing_provenance():
    """Verify that evaluator fails if emitted records lack cell provenance links."""
    fixture = get_fixture("fix_excel_simple_01")
    evaluator = DatasetEvaluator()

    # Records lack provenance_id
    records = [
        {
            "observation_key": f"obs_{i}",
            "signal_id": "SUCTION_PRESS" if i % 2 == 0 else "DISCHARGE_PRESS",
            "value_numeric": 10.0,
            "provenance_id": "",  # Missing provenance!
        }
        for i in range(1, 51)
    ]

    outcome = evaluator.evaluate(
        actual_result_state=JobResultState.ACCEPTED,
        actual_records=records,
        oracle=fixture,
    )

    assert outcome.passed is False
    assert outcome.provenance_missing_count == 50
    assert any("Provenance missing" in f for f in outcome.failures)


def test_evaluator_catches_false_acceptance():
    """Verify that evaluator flags when a defective file was wrongly marked ACCEPTED."""
    fail_fixture = get_fixture("fix_fail_corrupt_02")
    evaluator = DatasetEvaluator()

    outcome = evaluator.evaluate(
        actual_result_state=JobResultState.ACCEPTED,  # Critical false acceptance!
        actual_records=[],
        oracle=fail_fixture,
        actual_error_codes=[],
    )

    assert outcome.passed is False
    assert outcome.decision_match is False
    assert any("Decision mismatch" in f for f in outcome.failures)


def test_evaluator_catches_missing_error_code():
    """Verify that negative test cases verify the presence of specific error codes."""
    fail_fixture = get_fixture("fix_fail_traversal_01")
    evaluator = DatasetEvaluator()

    outcome = evaluator.evaluate(
        actual_result_state=JobResultState.FAILED,
        actual_records=[],
        oracle=fail_fixture,
        actual_error_codes=[ErrorCode.ERR_ADM_FILE_CORRUPT],  # Mismatched error code
    )

    assert outcome.passed is False
    assert outcome.error_codes_match is False
    assert any("Expected error codes missing" in f for f in outcome.failures)
