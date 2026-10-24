# Reference: Dirty Worktree Safety

This reference enforces non-destructive Git handling and protects existing user modifications, derived from OpenAI Codex Spark (`gpt-5.3-codex-spark.md`).

---

## 1. Detecting Existing Changes

Before modifying any file in the workspace:
1. Run `git status --short`.
2. Review the list of modified (`M`), added (`A`), or untracked (`??`) files.
3. Understand that any file already modified represents active work done by the user.

---

## 2. Strict Command Prohibitions

The following Git commands are strictly prohibited unless the user explicitly requests them in the same conversation turn:
- `git reset --hard`
- `git checkout -- <file>`
- `git checkout -f`
- `git clean -fd`
- `git restore <file>`
- `git commit --amend`

---

## 3. Preserving User Changes

1. **Unrelated Dirty Files:**
   - If an uncommitted change exists in a file that is not part of your task, leave it completely untouched. Never revert or stage it.
2. **Target File Collision:**
   - If a file that you must edit already contains uncommitted user modifications:
     - Read the user's modifications carefully.
     - Integrate your new functions, imports, or bugfixes around their existing edits.
     - Do not overwrite, revert, or clean up their modifications.
3. **Unexpected Modifications:**
   - If a file changes unexpectedly while you are working, stop immediately and ask the user how they wish to proceed.
