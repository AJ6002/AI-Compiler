# ADR-015: Investigation Output Contract as a Wrapper Around ParsePlan

## Status
ACCEPTED — IMPLEMENTED (Phase 1)

## Context
In the AICONNEX industrial compilation pipeline, deterministic discovery handles standard workbook topologies and routes ambiguous files to `REVIEW_REQUIRED`. When integrating an agentic sandbox investigation layer to resolve ambiguous structures:
1. The supervisor needs a formal contract for what the agent returns.
2. The initial proposal in Section 13.3 of the integration handoff stated "sandbox returns only a ParsePlan JSON".
3. However, returning *only* a `ParsePlan` is insufficient:
   - An LLM agent cannot express "I cannot resolve this ambiguity" or "human clarification is required for cell range X".
   - An agent cannot record the alternative layout hypotheses considered and rejected.
   - An agent cannot provide cell-level evidence references justifying why a header band or unpivot structure was chosen.
   - `ParsePlan` is an execution contract: immutable, strict (`extra="forbid"`), consumed directly by `PlanExecutor`. Mutating `ParsePlan` to include conversational notes, audit traces, or unresolved warnings pollutes the execution boundary.

## Decision
1. **Envelope Wrapper Pattern (`InvestigationResult`):**
   - We introduce `InvestigationResult` in `src/compiler/contracts/investigation.py` as an immutable wrapper around `ParsePlan`.
   - ParsePlan remains the sole contract consumed by PlanExecutor; InvestigationResult is a boundary artifact that carries the plan plus its rationale.
2. **First-Class Status State:**
   - `status: Literal["PLAN_PROPOSED", "REVIEW_REQUIRED"]` is an explicit, first-class state.
   - It is **not** inferred from `parse_plan is None`. In future iterations, an agent may propose a plan while flagging advisory issues, or produce evidence without a plan.
3. **Cross-Field Invariants Enforced at Schema Boundary:**
   - `status == "PLAN_PROPOSED"` strictly requires `parse_plan` to be non-null.
   - `status == "REVIEW_REQUIRED"` strictly requires `parse_plan` to be `None` and `unresolved` to contain at least one `UnresolvedIssue`.
   - The agent cannot issue a silent rejection without explicitly explaining *what* was ambiguous, in *which* file and sheet, and *what* clarification is needed.
4. **Audit Fields Isolated Outside Execution Plan:**
   - `alternate_interpretations_considered: list[str]` and `evidence_references: dict[str, str]` capture the agent's reasoning.
   - `agent_id` and `agent_version` capture model provenance.
   - These fields reside exclusively on `InvestigationResult`, ensuring zero footprint in downstream Parquet execution tables.
5. **Decoupled Bridge Helpers (`src/compiler/investigation/contract.py`):**
   - `unwrap_for_executor(result)`: Unpacks the inner `ParsePlan` only if `status == "PLAN_PROPOSED"`, raising an explicit `ValueError` naming the status otherwise.
   - `to_review_item(result, job_id)`: Bridges unresolved issues into the existing `ReviewItem` and `ReviewQueue` data steward domain with zero modifications to existing review queue code.

## Consequences
- **Security & Safety:** Untrusted agent output cannot inject arbitrary parameters into the execution engine; the plan must conform to `ParsePlan` and is unpacked through an allowlisted gate.
- **Auditability:** Stewards reviewing rejected workbooks see the exact cell coordinates, hypotheses, and required clarifications formulated by the agent.
- **Layer Independence:** The wrapper imports no sandbox, Docker, or model runtime dependencies; it is a pure contract layer testable in total isolation.
