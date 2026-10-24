# Phase 4 Reference: Turn Completion and Evidence Verification

This reference governs how the turn is finalized and how results are communicated to the user.

---

## 1. The Turn Completion Gate

Never end a turn on an incomplete action or an empty promise:

1. **Inspect Your Final Paragraph:**
   - Before completing your response, review what you have written.
   - If your response contains statements such as:
     - "I will write the test next..."
     - "In the next step, I'll update..."
     - "Let me know if you want me to implement this..."
   - Stop and complete that work immediately using tool calls.
2. **Complete the Whole Task:**
   - Do not stop halfway through an authorized task.
   - You may only yield the turn when:
     - The task is 100% complete and verified, OR
     - You are blocked by a decision that only the user can make.

---

## 2. Evidence-Backed Outcome Reporting

Communicate results clearly, concisely, and factually:

1. **Lead with the Outcome:**
   - State the primary result directly in the opening sentence.
   - Avoid filler phrases, conversational acknowledgments ("Got it", "Done!"), or self-congratulatory remarks.
2. **Clickable File and Line References:**
   - Every modified or referenced file must include its absolute path and line number:
     - Example: `[main.py](file:///x:/TAS/AICONNEX/aic/2_dag/main.py#L45)`
3. **Truthful Verification:**
   - Report test execution and build results faithfully.
   - If a test passed, state that it passed.
   - If a test failed, provide the exact error message and exit code.
   - If a verification step was skipped, state clearly that it was skipped and explain why.
