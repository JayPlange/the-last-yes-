#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import platform
import hashlib
import warnings
from datetime import datetime, timezone
from pathlib import Path
from last_yes.runner import run_benchmark
from last_yes.tasks import TASKS
from last_yes.authority_variants import AUTHORITY_VARIANTS
from last_yes.matched_authority import MATCHED_AUTHORITY_VARIANTS


def _format_percent(value: float | None) -> str:
    """Format a score without turning an unevaluated result into zero."""
    return "n/a" if value is None else f"{value:.1%}"


def format_model_summary(summary: dict) -> str:
    """Render scored trials separately from provider/harness errors."""
    model = summary["model"]
    passed = summary.get("passed_trials", 0)
    completed = summary.get("completed_trials", 0)
    attempted = summary.get("attempted_trials", summary.get("total_trials", 0))
    provider_errors = summary.get("provider_errors", 0)
    runner_errors = summary.get("runner_errors", 0)
    model_output_errors = summary.get("model_output_errors", 0)
    details = (
        f"attempted={attempted}, provider_errors={provider_errors}, "
        f"runner_errors={runner_errors}, model_output_errors={model_output_errors}"
    )
    coverage = _format_percent(summary.get("task_evaluation_coverage"))
    incidents = summary.get("root_incident_count", 0)
    return (
        f"{model}: {passed}/{completed} completed trials passed; {details}; "
        f"pass_rate={_format_percent(summary.get('pass_rate'))}; "
        f"task_coverage={coverage}; root_incidents={incidents}; "
        f"pass@k={_format_percent(summary.get('pass_at_k'))}; "
        f"pass^k={_format_percent(summary.get('pass_power_k'))}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run The Last Yes transaction-authorisation benchmark.")
    parser.add_argument("--models", nargs="+", help="Exact OpenRouter model IDs. Prefer a pinned provider/model:free or provider/model ID; openrouter/free is a dynamic router.")
    parser.add_argument("--repeat", type=int, default=2, help="Independent trials per task and model (default 2; use 3-5 for final evidence when quota permits).")
    parser.add_argument("--suite", choices=("core", "authority-variants", "matched-authority", "all"), default="core", help="Run the 10-task core suite (default), the 3 legacy exploratory variants, the 5 matched authority conditions, or all 18 tasks.")
    parser.add_argument("--only", nargs="*", help="Optional task IDs within the selected suite.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--out", type=Path, help="Report path. Default: results/run-<UTC timestamp>.json")
    parser.add_argument("--list-tasks", action="store_true")
    args = parser.parse_args()
    if args.suite == "core":
        suite_tasks = TASKS
    elif args.suite == "authority-variants":
        suite_tasks = AUTHORITY_VARIANTS
    elif args.suite == "matched-authority":
        suite_tasks = MATCHED_AUTHORITY_VARIANTS
    else:
        suite_tasks = TASKS + AUTHORITY_VARIANTS + MATCHED_AUTHORITY_VARIANTS
    if args.list_tasks:
        for task in suite_tasks:
            print(f"{task.id}: {task.title} ({len(task.turns)} turns)")
        return 0
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    known = {t.id for t in suite_tasks}
    only = set(args.only) if args.only else None
    if only and not only <= known:
        parser.error(f"Unknown task IDs: {', '.join(sorted(only - known))}")
    if not args.models:
        parser.error("--models is required unless --list-tasks is used")
    if "openrouter/free" in args.models:
        warnings.warn("openrouter/free may route different calls to different underlying models. Use only for a smoke test; do not report it as a single-model benchmark result.")
    started = datetime.now(timezone.utc)
    report = run_benchmark(args.models, args.repeat, only, args.temperature, tasks=suite_tasks)
    report["suite"] = args.suite
    finished = datetime.now(timezone.utc)
    report["started_utc"] = started.isoformat()
    report["finished_utc"] = finished.isoformat()
    report["runtime_environment"] = {"python": platform.python_version(), "platform": platform.platform()}
    root = Path(__file__).resolve().parent
    fingerprint_files = ["run_eval.py", "last_yes/tasks.py", "last_yes/authority_variants.py", "last_yes/matched_authority.py", "last_yes/agent.py", "last_yes/grader.py", "last_yes/simulator.py", "last_yes/runner.py"]
    digest = hashlib.sha256()
    for relative in fingerprint_files:
        digest.update(relative.encode("utf-8"))
        digest.update((root / relative).read_bytes())
    report["benchmark_bundle_sha256"] = digest.hexdigest()
    out = args.out or Path("results") / f"run-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out}")
    for summary in report["summaries"]:
        print(format_model_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
