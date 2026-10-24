# Phase 3 Reference: Decision-Complete Specification

This reference defines the required sections and level of detail for a decision-complete plan.

---

## 1. The Decision-Complete Standard

A plan is decision-complete when an implementer can execute the entire task without having to pause, guess, or invent architectural details:

1. **Concrete Interfaces and Schemas:**
   - Write out complete type definitions (such as Pydantic models, TypeScript interfaces, or SQL tables).
   - Write out exact endpoint routes, HTTP methods, headers, and status codes.
2. **Explicit Error States:**
   - Define all expected error scenarios.
   - Specify the exact exception classes to catch and the error payloads or logs to emit.
3. **Bounded Critical Files:**
   - Limit the implementation scope to the 3 to 5 most critical files.
   - List these files in the exact sequence in which they must be modified.

---

## 2. Standard Plan Output Format

Wrap the official plan in a `<proposed_plan>` block using GitHub Flavored Markdown:

```markdown
<proposed_plan>
# Plan: [Concise Feature or Bugfix Title]

## 1. Architectural Summary
- Objective: [One-sentence description of what will be achieved]
- Approach: [High-level architectural design and pattern alignment]

## 2. Interface and Schema Contracts
- Data Structures / Types:
  ```[language]
  [Exact Type Definition or Schema]
  ```
- Public APIs / Endpoints:
  - Route: `[METHOD] /api/v1/resource`
  - Request: `[Schema Name]`
  - Response (200 OK): `[Schema Name]`
  - Errors (400/404/500): `[Specific error condition and code]`

## 3. Implementation Sequence (Critical Files)
1. `path/to/first_file.ext`: [Specific functions and signatures to add or modify]
2. `path/to/second_file.ext`: [Specific callers or middleware to update]
3. `path/to/third_file.ext`: [Registration or route wiring]

## 4. Test and Acceptance Criteria
- Unit Test Case 1: [Input condition -> Expected output]
- Edge Case 2: [Invalid input condition -> Expected error code]
- Acceptance Command: [Exact terminal command to verify implementation, e.g. pytest path/to/test.py]

## 5. Locked Assumptions
- Assumption 1: [Default choice selected during Phase 2 trade-off resolution]
</proposed_plan>
```
