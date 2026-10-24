# Phase 2 Reference: Trade-off Clarification

This reference defines the protocol for resolving architectural decisions and business preferences.

---

## 1. Classification of Unknowns

Do not treat all missing information the same way:

| Category | Definition | Action Required |
|---|---|---|
| **Discoverable Facts** | Facts that exist in the codebase: schemas, types, file paths, dependency versions. | Explore the codebase silently. Never ask the user. |
| **Product Preferences** | Decisions that cannot be derived from code: business rules, backwards compatibility tolerance, user interface options. | Ask the user early using structured choices. |

---

## 2. Asking Trade-off Questions

When a question is required:

1. **Structured Multiple-Choice:**
   - Present 2 to 4 mutually exclusive options.
   - For each option, clearly explain the technical trade-off.
   - Designate one option as the **(Recommended)** choice and state the reason.
2. **Threshold for Asking:**
   - Only ask questions that materially alter the resulting code architecture or schema.
   - Do not ask trivial questions or questions regarding standard programming conventions.
3. **Defaulting Rule:**
   - If the user does not respond or asks you to make the judgment call, proceed with the recommended default and record it under the **Assumptions** section of the plan.
