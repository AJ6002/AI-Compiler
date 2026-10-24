# Phase 1 Reference: Non-Mutating Exploration

This reference governs how the agent discovers facts about the repository during the planning phase.

---

## 1. Ground in Repository Truth (Explore First, Ask Second)

Eliminate unknowns in the prompt by discovering facts in the code, not by questioning the user:

1. **Verify File Existence and Locations:**
   - Use targeted file searches (`rg`, specific directory lookups) to find existing classes, endpoints, and utilities.
   - Never ask the user where a file, class, or function is located when a search can answer it.
2. **Inspect Existing Design Patterns:**
   - Before designing a new module, locate an existing, working module in the same codebase.
   - Note its conventions: directory layout, file naming, export styles (named vs default), error handling, and type definitions.
3. **Inspect Dependency Manifests:**
   - Read dependency manifests (`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`).
   - Confirm which packages and versions are available. Do not propose solutions that require uninstalled third-party libraries without explicitly stating the requirement.

---

## 2. Prohibited Mutating Actions During Planning

Planning is strictly read-only:

1. **Disallowed Actions:**
   - Modifying or creating tracked files (no `write_to_file` or file edits).
   - Deleting files (no `rm` or deletion commands).
   - Running linters or formatters that write changes back to files.
   - Creating Git commits, branches, or worktrees.
2. **Allowed Non-Mutating Actions:**
   - Reading files and manifests.
   - Searching files and symbols (`rg`, `find`).
   - Reading Git history (`git log`, `git diff`, `git status`).
   - Running dry-run validation commands or static analysis commands that do not modify tracked files.
