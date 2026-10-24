# Reference: Codex Review Mindset

This reference embeds the exact code review directives from OpenAI Codex Spark (`gpt-5.3-codex-spark.md`).

---

## 1. Verbatim Code Review Mindset (Lines 28–29)

> **"If the user asks for a \"review\", default to a code review mindset: prioritise identifying bugs, risks, behavioural regressions, and missing tests. Findings must be the primary focus of the response - keep summaries or overviews brief and only after enumerating the issues. Present findings first (ordered by severity with file/line references), follow with open questions or assumptions, and offer a change-summary only as a secondary detail. If no findings are discovered, state that explicitly and mention any residual risks or testing gaps."**

---

## 2. Core Defect Priorities

When inspecting code lines, evaluate strictly in this hierarchy:

1. **Bugs (Defects in Existing Logic):**
   - Off-by-one index calculations.
   - Null pointer or undefined variable dereferences.
   - Unhandled exception states or broken error paths.
   - Incorrect mathematical calculations or logic inversions.
2. **Behavioral Regressions:**
   - Changes that break backwards compatibility for existing callers.
   - Altered return types, schema modifications, or modified default arguments.
   - Removed functions or reordered arguments that break external contracts.
3. **Risks (System Stability & Security):**
   - Unsanitized inputs leading to SQL injection or command execution risks.
   - Concurrency race conditions, missing locks, or unclosed database connections.
   - Unbounded memory consumption or infinite loops.
4. **Missing Tests & Untested Branches:**
   - Uncovered error branches in try/except blocks.
   - Edge cases (empty arrays, negative integers, null values) that lack assertions.

---

## 3. Explicit Negative Reporting

If no bugs or regressions are found after thorough line-by-line inspection:
1. Do not output vague praise.
2. State explicitly: *"No functional bugs or behavioral regressions identified in inspected lines."*
3. Enumerate the remaining residual risks:
   - Untested inputs or missing unit tests.
   - Unverified third-party service dependencies.
   - Concurrency or network timeout assumptions.
