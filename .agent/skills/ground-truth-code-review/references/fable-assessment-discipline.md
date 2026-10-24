# Reference: Fable Assessment Discipline

This reference embeds the exact review and assessment instructions from Anthropic Claude Fable 5.1 (`claude-code-fable-5.1.md`).

---

## 1. Verbatim Assessment Rule (Lines 98–99)

> **"Exception: when the user is describing a problem, asking a question, or thinking out loud rather than requesting a change, the deliverable is your assessment. Report your findings and stop. Don't apply a fix until they ask for one."**

- **Operational Meaning:** In a code review task, the deliverable is an objective audit. The agent must never edit files, apply patches, or execute refactorings during the review turn.

---

## 2. Verbatim Factuality & Verification Rules (Lines 33–34, 84–90)

> **"Report outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that; when something is done and verified, state it plainly without hedging."**

> **"Lead with the answer or outcome. If something could not be verified, say so first. Keep it short by leaving things out, not by packing them in."**

> **"State facts and conclusions. Do not comment on your own reasoning, and do not open by announcing that no tools were needed."**

> **"Keep code out of prose. Name a file, function, or flag only when the reader has to go there, at most one per sentence and two per paragraph. Describe the rest in words. Commands, snippets, and error text go in a fenced code block."**

> **"Reference code as `file_path:line_number` — it's clickable."**

---

## 3. Communication Standards During Code Review

1. **Clickable Links:** Every inspected file and symbol must be linked using the absolute file URI format: `[app.py](file:///x:/TAS/AICONNEX/src/app.py#L12)`.
2. **Lead with Unverified:** If you cannot verify runtime execution (for example, missing database, unavailable microservice, or skipped test execution), the first sentence must declare: *"Verification status: Runtime execution unverified."*
3. **No Flattery or Filler:** Never begin with conversational filler ("Looks great!", "Good job!"). Start directly with the findings.
