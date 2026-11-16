#!/usr/bin/env python3
"""Validate the independent gold-policy traces against the deterministic grader."""
from __future__ import annotations
import json
from pathlib import Path
from last_yes.reference import validate_references


def main() -> int:
    outcomes = validate_references()
    report = {
        "benchmark": "The Last Yes",
        "validation_type": "reference_policy_validation_not_model_results",
        "task_count": len(outcomes),
        "passed_tasks": sum(1 for row in outcomes if row["passed"]),
        "all_passed": all(row["passed"] for row in outcomes),
        "outcomes": outcomes,
    }
    target = Path("results") / "reference-validation.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Reference validation: {report['passed_tasks']}/{report['task_count']} passed")
    print(f"Wrote {target}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
