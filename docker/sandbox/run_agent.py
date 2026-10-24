"""Deterministic test runner inside sandbox reading /input/brief.json and writing /output/result.json."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    input_dir = Path("/input")
    output_dir = Path("/output")
    brief_path = input_dir / "brief.json"
    result_path = output_dir / "result.json"

    if not brief_path.exists():
        sys.stderr.write(f"Missing required brief at {brief_path}\n")
        return 1

    try:
        with open(brief_path, "r", encoding="utf-8") as f:
            brief = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Malformed brief JSON: {exc}\n")
        return 2

    # The brief can optionally provide a canned result to emit
    canned_result = brief.get("canned_result")
    if canned_result is None:
        canned_result = {
            "schema_version": "1.0.0",
            "tenant_id": brief.get("tenant_id", "system"),
            "project_id": brief.get("project_id", "system"),
            "agent_id": "agent:deterministic_runner",
            "agent_version": "1.0.0",
            "status": "REVIEW_REQUIRED",
            "parse_plan": None,
            "unresolved": [
                {
                    "tenant_id": brief.get("tenant_id", "system"),
                    "project_id": brief.get("project_id", "system"),
                    "issue": "Default unresolved investigation result",
                    "source_file": brief.get("file_name", "unknown.xlsx"),
                    "sheet": "Sheet1",
                    "cell_range": "A1:Z100",
                    "required_clarification": "Human review required",
                }
            ],
            "alternate_interpretations_considered": [],
            "evidence_references": {},
        }

    try:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(canned_result, f, indent=2)
    except Exception as exc:
        sys.stderr.write(f"Failed to write output result: {exc}\n")
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
