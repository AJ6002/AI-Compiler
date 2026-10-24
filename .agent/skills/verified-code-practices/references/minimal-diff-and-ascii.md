# Reference: Minimal Diff and ASCII Editing

This reference defines rules for file modifications, character sets, and editing efficiency, derived from OpenAI Codex Spark (`gpt-5.3-codex-spark.md`).

---

## 1. ASCII Defaults

1. **Character Set Standard:**
   - Default to plain ASCII characters when editing existing files or creating new files.
   - Do not use non-ASCII or Unicode characters (such as smart quotes, em-dashes, or non-standard symbols) unless the file already uses them.
2. **File Creation:**
   - Write files with standard UTF-8 encoding without byte-order marks (BOM).

---

## 2. Minimal Necessary Diff

1. **Zero Unprompted Refactoring:**
   - Only modify code that is directly required to solve the task or fix the bug.
   - Do not reformat code in surrounding functions.
   - Do not rename variables or reorder imports in untouched code.
2. **Preserve Existing Comments:**
   - Keep all existing comments, docstrings, and license headers intact unless the user explicitly requests their modification.

---

## 3. Strict Single-Pass Reading

1. **Identify Targets First:**
   - Identify the exact files that must be modified before reading them.
2. **Read Once per Task:**
   - Read each target file once to capture its structure and line numbers.
   - Do not execute repetitive read commands on files already inspected during the current turn.
3. **Decisive Application:**
   - Prepare all replacements in memory and apply them in a single batch.
