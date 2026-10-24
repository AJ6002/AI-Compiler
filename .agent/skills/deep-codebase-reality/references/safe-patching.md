# Phase 3 Reference: Atomic Safe Patching

This reference governs how files are modified, ensuring that user work is preserved and changes remain tightly focused.

---

## 1. Dirty Git Worktree Protection

Real-world development environments frequently have uncommitted user edits. Treat the user's workspace with extreme caution:

1. **Detect Uncommitted Work:**
   - Before executing code edits, run `git status --short` to see all modified or untracked files.
2. **Never Revert User Work:**
   - NEVER run destructive git commands like `git checkout -- .`, `git reset --hard`, or `git restore .`.
   - If an uncommitted change was made by the user in a file you do not need to touch, leave that file alone.
   - If an uncommitted change was made by the user in a file you MUST edit:
     - Read the user's edits carefully.
     - Integrate your new logic around their changes without deleting their code.
3. **Unexpected File Modifications:**
   - If files change unexpectedly during your turn, stop immediately and verify with the user before proceeding.

---

## 2. Scope Preservation Rule

Deliver exactly what was asked—no more, no less:

1. **Zero Unrequested Refactoring:**
   - Do not reformat files that are outside your immediate edit target.
   - Do not rename existing variables, functions, or imports for aesthetic preferences.
   - Do not rewrite legacy patterns into new patterns unless the user specifically asked for a refactor.
2. **Minimal Necessary Diff:**
   - Make the smallest, cleanest change that completely solves the problem.
   - Keep unchanged functions, comments, docstrings, and license headers intact.

---

## 3. Atomic Single-Patch Execution

1. **Plan All Edits First:**
   - Formulate the exact edits, target files, line numbers, and replacement blocks in reasoning before executing the tool calls.
2. **Apply in One Pass:**
   - Apply edits decisively.
   - Avoid executing repeated cycles of small edits followed by immediate read-checks.
3. **Failure Handling:**
   - If an edit fails due to a line-mismatch or conflict, read only the failing line range to adjust the replacement target.
