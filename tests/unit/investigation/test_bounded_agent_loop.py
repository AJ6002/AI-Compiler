"""Unit tests for InvestigationAgent loop, budget ceilings, and gate re-execution."""

from pathlib import Path

import pytest

from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import DuplicatePolicy, JobResultState, PartialBatchPolicy
from src.compiler.investigation.agent import (
    InvestigationAgent,
    InvestigationBudget,
)
from src.compiler.investigation.model_client import (
    DeterministicFakeModelClient,
    ModelResponse,
)
from src.compiler.investigation.residency import ModelResidency, ResidencyPolicy
from src.compiler.readers.openpyxl_reader import OpenpyxlReader


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "golden" / "fixtures"


@pytest.fixture
def basic_contract() -> ClientContract:
    return ClientContract(
        tenant_id="tenant-inv",
        project_id="proj-inv",
        contract_id="contract-inv-01",
        version="1.0.0",
        expected_assets=["COMP_A", "DEFAULT_ASSET"],
        required_signals=["SUCTION_PRESS", "OIL_PRESS"],
        allowed_units={},
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )


def test_agent_prohibited_residency_routes_to_review(
    fixtures_dir: Path, basic_contract: ClientContract
) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-inv", "proj-inv", max_preview_rows=15)

    agent = InvestigationAgent()
    policy = ResidencyPolicy(
        tenant_id="tenant-inv",
        project_id="proj-inv",
        residency=ModelResidency.PROHIBITED,
    )

    result = agent.investigate(
        source=xlsx_path,
        structure=structure,
        contract=basic_contract,
        target_object_id="obj_test",
        residency_policy=policy,
    )

    assert not result.residency_allowed
    assert result.verdict == JobResultState.REVIEW_REQUIRED
    assert result.proposed_plan is None
    assert result.audit.tool_calls_executed == 0


def test_agent_successful_investigation_and_validation(
    fixtures_dir: Path, basic_contract: ClientContract
) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-inv", "proj-inv", max_preview_rows=15)

    agent = InvestigationAgent()
    policy = ResidencyPolicy(
        tenant_id="tenant-inv",
        project_id="proj-inv",
        residency=ModelResidency.CLOUD_AUTHORIZED,
        allowed_providers=["fake"],
    )

    result = agent.investigate(
        source=xlsx_path,
        structure=structure,
        contract=basic_contract,
        target_object_id="obj_test",
        residency_policy=policy,
    )

    assert result.residency_allowed
    assert result.proposed_plan is not None
    assert result.audit.tool_calls_executed == 2
    assert result.verdict == JobResultState.ACCEPTED
    assert result.validation_report is not None
    assert result.validation_report.result_state == JobResultState.ACCEPTED


def test_agent_budget_exhaustion_halts_loop(
    fixtures_dir: Path, basic_contract: ClientContract
) -> None:
    xlsx_path = fixtures_dir / "excel_simple" / "simple_table_ltds.xlsx"
    reader = OpenpyxlReader()
    structure = reader.inspect(xlsx_path, "tenant-inv", "proj-inv", max_preview_rows=15)

    # Client that only calls list_sheets in an infinite loop without proposing a plan
    infinite_tool_responses = [
        ModelResponse(
            content="Listing sheets again...",
            tool_calls=[
                {"id": f"call_{i}", "function": {"name": "list_sheets", "arguments": "{}"}}
            ],
            tokens_used=50,
        )
        for i in range(20)
    ]
    fake_client = DeterministicFakeModelClient(scripted_responses=infinite_tool_responses)
    agent = InvestigationAgent(model_client=fake_client)

    policy = ResidencyPolicy(
        tenant_id="tenant-inv",
        project_id="proj-inv",
        residency=ModelResidency.SELF_HOSTED,
    )

    # Cap budget at max 3 tool calls
    tight_budget = InvestigationBudget(max_tool_calls=3)

    result = agent.investigate(
        source=xlsx_path,
        structure=structure,
        contract=basic_contract,
        target_object_id="obj_test",
        residency_policy=policy,
        budget=tight_budget,
    )

    # Loop halted when tool calls reached budget max (3)
    assert result.audit.tool_calls_executed == 3
    assert result.verdict == JobResultState.REVIEW_REQUIRED
    assert result.proposed_plan is None
