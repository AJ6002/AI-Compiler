"""Provider-neutral model client interface and deterministic fake for testing."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ModelMessage(BaseModel):
    """Message payload for model investigation conversations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant", "tool"] = Field(...)
    content: str = Field(...)
    tool_call_id: str | None = Field(default=None)
    tool_calls: list[dict[str, Any]] | None = Field(default=None)


class ModelResponse(BaseModel):
    """Normalized response from a model provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str | None = Field(default=None)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tokens_used: int = Field(default=0, ge=0)


class ModelClient(Protocol):
    """Provider-neutral client protocol satisfied by self-hosted or cloud LLMs."""

    def generate(
        self,
        messages: list[ModelMessage],
        tools: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Produce a response or tool call requests based on conversation history."""
        ...


class DeterministicFakeModelClient:
    """Deterministic mock model client for testing investigation loops and tool bounds.

    Cycles through a pre-defined queue of responses or executes a standard
    investigation sequence without making any network calls.
    """

    def __init__(self, scripted_responses: list[ModelResponse] | None = None) -> None:
        self._responses = list(scripted_responses or [])
        self._call_count = 0

    def generate(
        self,
        messages: list[ModelMessage],
        tools: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Return scripted response or default tool sequence."""
        self._call_count += 1

        if self._responses:
            return self._responses.pop(0)

        # Default scripted sequence:
        # Call 1: list_sheets
        if self._call_count == 1:
            return ModelResponse(
                content="Inspecting available worksheets.",
                tool_calls=[
                    {
                        "id": "call_1",
                        "function": {
                            "name": "list_sheets",
                            "arguments": "{}",
                        },
                    }
                ],
                tokens_used=120,
            )

        # Call 2: propose a basic parse plan
        plan_json = (
            '{"sheet_name": "SimpleReadings", "operations": ['
            '{"op": "select_region", "params": '
            '{"min_row": 1, "max_row": 51, "min_col": 1, "max_col": 9}}, '
            '{"op": "flatten_headers", "params": {"header_rows": [1], "separator": "."}}, '
            '{"op": "unpivot", "params": '
            '{"id_vars": ["DATE"], "value_vars": ["SUCTION_PRESS", "OIL_PRESS"]}}'
            "]}"
        )
        return ModelResponse(
            content="Proposing default parse plan for target sheet.",
            tool_calls=[
                {
                    "id": "call_2",
                    "function": {
                        "name": "propose_parse_plan",
                        "arguments": plan_json,
                    },
                }
            ],
            tokens_used=240,
        )
