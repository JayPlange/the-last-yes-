#!/usr/bin/env python3
"""Merge repeated runs of the same fixed benchmark/model set into one report."""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def merge_reports(paths: list[Path]) -> dict[str, Any]:
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if len(reports) < 2:
        raise ValueError("Provide at least two run reports to merge")
    identity_keys = ("benchmark", "version", "models", "temperature", "task_count", "turn_count", "benchmark_bundle_sha256")
    first = reports[0]
    expected_task_ids = {row.get("task_id") for row in first.get("results", [])}
    for path, report in zip(paths[1:], reports[1:]):
        for key in identity_keys:
            if report.get(key) != first.get(key):
                raise ValueError(f"Cannot merge {path}: field {key!r} differs from {paths[0]}")
        report_task_ids = {row.get("task_id") for row in report.get("results", [])}
        if report_task_ids != expected_task_ids:
            raise ValueError(f"Cannot merge {path}: task IDs differ from {paths[0]}")

    merged_rows = []
    trial_counts: dict[tuple[str, str], int] = defaultdict(int)
    for path, report in zip(paths, reports):
        for original in report.get("results", []):
            row = dict(original)
            key = (row.get("model", ""), row.get("task_id", ""))
            trial_counts[key] += 1
            row["trial"] = trial_counts[key]
            row["source_report"] = path.name
            merged_rows.append(row)

    models = list(first["models"])
    task_ids = sorted({row["task_id"] for row in merged_rows})
    counts = {trial_counts[(model, task)] for model in models for task in task_ids}
    if len(counts) != 1:
        raise ValueError("Runs do not contain the same number of trials for every model/task pair")
    repeats = counts.pop() if counts else 0

    summaries = []
    for model in models:
        model_rows = [r for r in merged_rows if r["model"] == model]
        completed_rows = [r for r in model_rows if r.get("status", "completed") == "completed"]
        per_task = []
        for task_id in task_ids:
            task_rows = [r for r in model_rows if r["task_id"] == task_id]
            valid_rows = [r for r in task_rows if r.get("status", "completed") == "completed"]
            passed = sum(1 for r in valid_rows if r.get("passed") is True)
            valid_count = len(valid_rows)
            per_task.append({
                "task_id": task_id,
                "passed_trials": passed,
                "trials": valid_count,
                "attempted_trials": len(task_rows),
                "completion_rate": valid_count / len(task_rows) if task_rows else None,
                "provider_errors": sum(1 for r in task_rows if r.get("status") == "provider_error"),
                "runner_errors": sum(1 for r in task_rows if r.get("status") == "runner_error"),
                "model_output_errors": sum(1 for r in valid_rows if r.get("model_output_error")),
                "pass_rate": passed / valid_count if valid_count else None,
                "pass_at_k": (1.0 if passed else 0.0) if valid_count else None,
                "pass_power_k": (1.0 if passed == repeats else 0.0) if valid_count == repeats else None,
            })
        evaluated_tasks = [row for row in per_task if row["trials"] > 0]
        fully_repeated = [row for row in per_task if row["trials"] == repeats]
        incident_rows = [
            (result, incident)
            for result in model_rows
            for incident in result.get("incidents", [])
        ]
        incident_type_counts: dict[str, int] = {}
        for _result, incident in incident_rows:
            incident_id = str(incident.get("id", "unknown"))
            incident_type_counts[incident_id] = incident_type_counts.get(incident_id, 0) + 1
        trials_with_incidents = {
            (row.get("task_id"), row.get("trial")) for row, _incident in incident_rows
        }
        usage = [u for r in model_rows for u in r.get("usage", [])]
        served_models = sorted({u["served_model"] for u in usage if u.get("served_model")})
        costs_known = all(u.get("cost") is not None for u in usage)
        passed_runs = sum(1 for r in completed_rows if r.get("passed") is True)
        summaries.append({
            "model": model,
            "served_models": served_models,
            "mixed_model_route": len(served_models) > 1,
            "unreported_served_model_calls": sum(1 for u in usage if not u.get("served_model")),
            "passed_trials": passed_runs,
            "completed_trials": len(completed_rows),
            "attempted_trials": len(model_rows),
            "total_trials": len(model_rows),
            "provider_errors": sum(1 for r in model_rows if r.get("status") == "provider_error"),
            "runner_errors": sum(1 for r in model_rows if r.get("status") == "runner_error"),
            "model_output_errors": sum(1 for r in completed_rows if r.get("model_output_error")),
            "pass_rate": passed_runs / len(completed_rows) if completed_rows else None,
            "trial_completion_rate": len(completed_rows) / len(model_rows) if model_rows else None,
            "evaluated_task_count": len(evaluated_tasks),
            "task_evaluation_coverage": len(evaluated_tasks) / len(task_ids) if task_ids else None,
            "fully_repeated_task_count": len(fully_repeated),
            "root_incident_count": len(incident_rows),
            "trials_with_root_incidents": len(trials_with_incidents),
            "root_incidents_by_type": dict(sorted(incident_type_counts.items())),
            "pass_at_k": sum(1 for row in evaluated_tasks if row["passed_trials"] > 0) / len(evaluated_tasks) if evaluated_tasks else None,
            "pass_power_k": sum(1 for row in fully_repeated if row["passed_trials"] == repeats) / len(fully_repeated) if len(fully_repeated) == len(task_ids) and task_ids else None,
            "per_task": per_task,
            "total_elapsed_ms": sum(r.get("elapsed_ms", 0) for r in model_rows),
            "usage_cost_usd": sum((u.get("cost") or 0) for u in usage) if costs_known else (0 if not usage else None),
        })

    started_values = [r.get("started_utc") for r in reports if r.get("started_utc")]
    finished_values = [r.get("finished_utc") for r in reports if r.get("finished_utc")]
    return {
        **{key: first.get(key) for key in identity_keys},
        "repeats": repeats,
        "started_utc": min(started_values) if started_values else None,
        "finished_utc": max(finished_values) if finished_values else None,
        "merged_from": [path.name for path in paths],
        "runtime_environments": [r.get("runtime_environment") for r in reports if r.get("runtime_environment")],
        "summaries": summaries,
        "results": merged_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path, help="Run JSON reports from the same benchmark version/model set")
    parser.add_argument("--out", type=Path, default=Path("results/combined.json"))
    args = parser.parse_args()
    try:
        report = merge_reports(args.reports)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Merged {len(args.reports)} reports into {args.out}")
    for summary in report["summaries"]:
        at_k = f"{summary['pass_at_k']:.1%}" if summary["pass_at_k"] is not None else "n/a"
        power_k = f"{summary['pass_power_k']:.1%}" if summary["pass_power_k"] is not None else "n/a"
        print(f"{summary['model']}: {summary['passed_trials']}/{summary['completed_trials']} completed trials passed "
              f"({summary['provider_errors']} provider errors, {summary['runner_errors']} runner errors, "
              f"{summary.get('model_output_errors', 0)} model-output errors); "
              f"task_coverage={summary.get('task_evaluation_coverage', 0):.1%}; "
              f"root_incidents={summary.get('root_incident_count', 0)}; "
              f"pass@k={at_k}; pass^k={power_k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
