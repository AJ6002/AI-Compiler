# Phase 4 Reference: Pre-Work Advisor Audit

This reference provides a pre-implementation verification gate to ensure the plan is technically valid before execution starts.

---

## 1. Adversarial Plan Review

Before presenting the plan as complete, evaluate the plan against these 5 checks:

1. **Existence Verification:**
   - Do all referenced base files actually exist on disk at the exact paths specified?
   - Do all referenced functions, base classes, or modules exist in the codebase?
2. **Dependency Feasibility:**
   - Are any uninstalled packages or unsupported runtime versions introduced?
   - If a new library is required, is its installation explicitly accounted for in the plan?
3. **Caller Integrity:**
   - Does changing an existing function signature break other callers in the codebase?
   - If breaking changes are required, are all callers included in the critical files list?
4. **Scope Sanity:**
   - Does the plan stay focused on the user's core request?
   - Has any speculative refactoring or unrequested cleanup crept into the tasks?
5. **Decision Completeness:**
   - Could an implementer encounter an ambiguous choice during execution?
   - If yes, resolve that ambiguity directly in the plan before finalizing.

---

## 2. Handoff to Implementation

Once the plan passes the Advisor Audit:
1. Render the `<proposed_plan>` block to the user.
2. Direct the next phase to [`deep-codebase-reality`](file:///x:/TAS/AICONNEX/.agent/skills/deep-codebase-reality/SKILL.md) for single-pass code execution.
