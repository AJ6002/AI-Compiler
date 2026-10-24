# Reference: Turn Completion Discipline

This reference enforces the turn-completion gate and eliminates unfulfilled promises, derived from Claude Fable 5.1 (`claude-code-fable-5.1.md`).

---

## 1. The Turn Completion Gate

1. **Inspect Your Final Paragraph:**
   - Before ending your turn, review the proposed final paragraph.
   - If it contains statements such as:
     - *"I will implement the rest of the function next..."*
     - *"In the next step, I will add the missing test..."*
     - *"Let me know if you would like me to fix this error..."*
   - Execute that work immediately using tool calls instead of yielding the turn.
2. **Finish the Entire Authorized Scope:**
   - Deliver the complete requested work, not only the straightforward parts.
   - You may stop and yield the turn only when:
     - All authorized work is 100% complete and verified, OR
     - You are blocked by a decision that only the user can make.

---

## 2. Clickable File References

1. **Formatting Rules:**
   - When referencing a modified or inspected file, use an absolute path with line numbers using the file URI scheme:
     `[filename.py](file:///x:/TAS/AICONNEX/src/filename.py#L25)`
   - Never reference nonexistent file paths.
