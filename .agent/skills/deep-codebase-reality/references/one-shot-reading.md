# Phase 2 Reference: One-Shot Context Acquisition

This reference defines rules for reading source code with high speed, accuracy, and zero redundancy.

---

## 1. Strict One-Shot Reading Principle

Every file inspection has a performance and context cost. Adhere strictly to the single-pass inspection protocol:

1. **Pre-Identify Target Files:**
   - Based on Phase 1 architectural discovery, list the exact files that must be read.
   - Do not perform wide, unguided directory scans (such as `ls -R` or `Get-ChildItem -Recurse`).
   - Use targeted search tools (`rg` or specific file path lookups) to find file paths directly.
2. **Read Once, Understand Completely:**
   - Read each required file once.
   - Extract the entire structural context in that single read:
     - Class definitions and function signatures.
     - Type annotations and schema definitions.
     - Variable scopes and dependencies.
     - Exact line numbers of the code sections you need to edit.
3. **No Redundant Re-Reading:**
   - Do not re-read a file you have already inspected in the same task.
   - The only acceptable reason to re-read a file is a hard failure (such as an edit conflict error or a failed patch application).

---

## 2. Temporal and Fact Verification

To prevent hallucinations and incorrect assumptions:

1. **Inspect Before Assuming:**
   - Before referencing an imported function or external package, confirm that it actually exists in the file or project dependencies.
   - Do not invent hypothetical method names or parameters.
2. **Extract Exact Signatures:**
   - Note the exact names, argument orders, and default values of all functions you intend to call.
   - Keep note of line numbers so subsequent edits can target exact line ranges without guessing.
