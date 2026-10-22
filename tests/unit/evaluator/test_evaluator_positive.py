from pathlib import Path

from src.compiler.contracts.enums import JobResultState
from src.compiler.evaluator import CorpusCatalog, DatasetEvaluator


def test_corpus_catalog_loading():
    """Verify that the master corpus catalog loads and validates all 7 categories."""
    catalog_path = Path("tests/golden/manifests/corpus_catalog.json")
    assert catalog_path.is_file()

    catalog = CorpusCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    assert catalog.schema_version == "1.0.0"
    assert len(catalog.fixtures) == 8

    # Verify all 7 categories are represented
    categories = {f.category for f in catalog.fixtures}
    assert len(categories) == 7


def test_evaluator_positive_match():
    """Verify that a compliant dataset passes evaluation cleanly."""
    catalog_path = Path("tests/golden/manifests/corpus_catalog.json")
    catalog = CorpusCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    simple_fixture = next(f for f in catalog.fixtures if f.fixture_id == "fix_excel_simple_01")

    # Generate compliant actual records matching oracle
    actual_records = [
        {
            "observation_key": f"obs_{i}",
            "signal_id": "SUCTION_PRESS" if i % 2 == 0 else "DISCHARGE_PRESS",
            "value_numeric": 12.5,
            "provenance_id": f"SimpleReadings!A{i}",
        }
        for i in range(1, 51)
    ]

    evaluator = DatasetEvaluator()
    outcome = evaluator.evaluate(
        actual_result_state=JobResultState.ACCEPTED,
        actual_records=actual_records,
        oracle=simple_fixture,
    )

    assert outcome.passed is True
    assert outcome.decision_match is True
    assert outcome.row_count_match is True
    assert outcome.signal_coverage_match is True
    assert len(outcome.failures) == 0
