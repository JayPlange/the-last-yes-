"""Run the fixed task set against one or more OpenRouter models."""
from __future__ import annotations
import json
import time
from typing import Any
from .agent import SYSTEM_PROMPT, OpenRouterError, chat_completion
from .grader import grade
from .simulator import CommerceSimulator
from .tasks import TASKS, Task


def _parse_tool_call_arguments(arguments: Any, index: int) -> dict[str, Any]:
    """Parse provider-returned arguments without attempting heuristic repair.

    A completed assistant response with malformed tool arguments is a
    scoreable model/provider-output failure, not a local runner failure.
    Never repair malformed JSON: doing so could silently change the action
    the model actually requested.
    """
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"tool_calls[{index}].function.arguments is not valid JSON: {exc.msg}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ValueError(
                f"tool_calls[{index}].function.arguments must encode a JSON object"
            )
        return parsed
    raise ValueError(
        f"tool_calls[{index}].function.arguments must be an object or JSON string"
    )


def _normalise_tool_calls_for_history(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return OpenAI-compatible tool calls for the next chat-history request.

    Some OpenRouter provider adapters (observed with Cohere) return
    ``function.arguments`` as an already-decoded object. The OpenAI-compatible
    chat-completions request format requires this field to be a JSON string.
    Preserve the raw provider response in the audit transcript, but send a
    canonicalised copy back to the API so multi-turn tool conversations work
    across providers.
    """
    normalised: list[dict[str, Any]] = []
    for index, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            raise ValueError(f"tool_calls[{index}] must be an object")
        function = call.get("function")
        if not isinstance(function, dict):
            raise ValueError(f"tool_calls[{index}].function must be an object")
        arguments = function.get("arguments", "{}")
        _parse_tool_call_arguments(arguments, index)
        if isinstance(arguments, dict):
            arguments_text = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
        else:
            arguments_text = arguments

        normalised_call = dict(call)
        normalised_function = dict(function)
        normalised_function["arguments"] = arguments_text
        normalised_call["function"] = normalised_function
        normalised.append(normalised_call)
    return normalised


def run_trial(task: Task, model: str, trial: int, temperature: float = 0.0) -> dict[str, Any]:
    sim = CommerceSimulator(task)
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    transcript: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    start = time.perf_counter()
    error = None
    status = "completed"
    model_output_error: dict[str, Any] | None = None

    for index, turn in enumerate(task.turns):
        sim.set_turn(index, turn.user)
        messages.append({"role": "user", "content": turn.user})
        try:
            assistant, usage = chat_completion(model, messages, temperature=temperature)
            usage_rows.append(usage)
        except OpenRouterError as exc:
            # Provider/API failures are not evidence about model capability.
            # Preserve the attempt in the report but exclude it from score denominators.
            status = "provider_error"
            error = f"{type(exc).__name__}: {exc}"
            transcript.append({"turn": index, "user": turn.user, "error": error})
            break
        except Exception as exc:  # harness/runtime faults are also not model evidence
            status = "runner_error"
            error = f"{type(exc).__name__}: {exc}"
            transcript.append({"turn": index, "user": turn.user, "error": error})
            break

        content = assistant.get("content")
        tool_calls = assistant.get("tool_calls") or []
        if not isinstance(tool_calls, list):
            # A successful API completion with malformed model output is scoreable
            # as a model failure, unlike a provider/API error.
            error = "Model returned malformed tool_calls (expected a list)"
            transcript.append({"turn": index, "user": turn.user, "error": error})
            break
        turn_record: dict[str, Any] = {"turn": index, "user": turn.user, "assistant_content": content, "tool_calls": []}
        if turn.assistant_after:
            turn_record["scenario_controlled_assistant_context"] = turn.assistant_after
        if tool_calls:
            # Preserve the exact model-generated tool calls in the audit transcript.
            # The earlier version executed these calls but left turn_record["tool_calls"]
            # empty, making successful tool use harder to independently inspect.
            turn_record["tool_calls"] = tool_calls
            # Validate every returned tool call before history normalisation
            # or simulator execution. Malformed arguments from a completed
            # assistant response are a scoreable model/provider-output failure.
            # Preserve them verbatim and never attempt risky JSON repair.
            invalid_tool_call = None
            for call_index, call in enumerate(tool_calls):
                if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                    invalid_tool_call = {
                        "index": call_index,
                        "raw_tool_call": call,
                        "reason": f"tool_calls[{call_index}] must contain a function object",
                    }
                    break
                function = call["function"]
                try:
                    _parse_tool_call_arguments(function.get("arguments", "{}"), call_index)
                except ValueError as exc:
                    invalid_tool_call = {
                        "index": call_index,
                        "tool_name": function.get("name"),
                        "raw_arguments": function.get("arguments"),
                        "reason": str(exc),
                    }
                    break
            if invalid_tool_call is not None:
                error = "Malformed model tool-call output: " + invalid_tool_call["reason"]
                model_output_error = invalid_tool_call
                transcript.append({**turn_record, "error": error, "model_output_error": invalid_tool_call})
                # A model response was received, so this is a completed and
                # scoreable failed trial. No malformed action is executed.
                break

            # Some adapters return decoded dict arguments. Convert only valid
            # objects to JSON strings in the next API request's history while
            # retaining the exact raw response in the transcript.
            try:
                history_tool_calls = _normalise_tool_calls_for_history(tool_calls)
            except ValueError as exc:
                # This is a local harness fault if reached: input was already
                # validated immediately above.
                status = "runner_error"
                error = f"Tool-call history normalisation failed: {exc}"
                transcript.append({**turn_record, "error": error})
                break
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": history_tool_calls,
            })
            tool_results = []
            visible = None
            for call in tool_calls:
                if not isinstance(call, dict):
                    call = {}
                function = call.get("function") or {}
                if not isinstance(function, dict):
                    function = {}
                name = function.get("name", "")
                raw_args = function.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    if not isinstance(args, dict):
                        args = {}
                except (TypeError, json.JSONDecodeError):
                    args = {}
                result = sim.execute(name, args)
                tool_result_text = json.dumps(result, ensure_ascii=False)
                tool_call_id = call.get("id")
                if not isinstance(tool_call_id, str) or not tool_call_id:
                    tool_call_id = f"call-{index}-{len(tool_results)}"
                messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": tool_result_text})
                tool_results.append({"tool": name, "arguments": args, "result": result})
                visible = sim.customer_message_for(result)
            # KasaFlow-inspired design: the application, not another LLM
            # completion, renders a deterministic customer-facing result.
            visible = turn.assistant_after or visible or (content or "I could not complete that request.")
            messages.append({"role": "assistant", "content": visible})
            sim.visible_messages.append(visible)
            turn_record["tool_results"] = tool_results
            turn_record["customer_visible_reply"] = visible
        else:
            visible = content if isinstance(content, str) else ""
            messages.append({"role": "assistant", "content": visible})
            sim.visible_messages.append(visible)
            turn_record["customer_visible_reply"] = visible
            turn_record["orders_existing_when_replied"] = len(sim.orders)
        if turn.assistant_after and not tool_calls:
            # Controlled context is only injected for a specified test case.
            messages.append({"role": "assistant", "content": turn.assistant_after})
        transcript.append(turn_record)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    if status == "completed" and model_output_error is not None:
        result = {
            "task_id": task.id,
            "passed": False,
            "checks": [{
                "id": "tool_call_arguments_are_valid_json_objects",
                "passed": False,
                "expected": "Each function.arguments value must be a valid JSON object (or decoded object).",
                "actual": model_output_error.get("raw_arguments"),
                "reason": model_output_error["reason"],
            }],
            "event_count": len(sim.events),
            "order_count": len(sim.orders),
            "model_output_error": model_output_error,
            "incidents": [],
            "incident_count": 0,
        }
    elif status == "completed":
        result = grade(task, sim, transcript)
    else:
        # An incomplete attempt has no model-performance score. Do not run the
        # grader against an empty/partial transcript: that would manufacture
        # misleading failed checks from a provider or harness outage.
        result = {
            "task_id": task.id,
            "passed": None,
            "checks": [],
            "event_count": len(sim.events),
            "order_count": len(sim.orders),
            "not_evaluated_reason": status,
            "incidents": [],
            "incident_count": 0,
        }
    result.update({
        "status": status,
        "model": model,
        "served_models": sorted({u["served_model"] for u in usage_rows if u.get("served_model")}),
        "unreported_served_model_calls": sum(1 for u in usage_rows if not u.get("served_model")),
        "trial": trial,
        "temperature": temperature,
        "error": error,
        "elapsed_ms": elapsed_ms,
        "usage": usage_rows,
        "transcript": transcript,
        "events": sim.events,
        "final_state": sim.final_state(),
    })
    if error and status == "completed":
        result["passed"] = False
    return result


def run_benchmark(models: list[str], repeats: int = 3, only: set[str] | None = None,
                  temperature: float = 0.0, tasks: tuple[Task, ...] | None = None) -> dict[str, Any]:
    task_set = TASKS if tasks is None else tasks
    selected = [task for task in task_set if only is None or task.id in only]
    results = []
    for model in models:
        for task in selected:
            for trial in range(1, repeats + 1):
                results.append(run_trial(task, model, trial, temperature))
    summaries = []
    for model in models:
        model_rows = [r for r in results if r["model"] == model]
        completed_rows = [r for r in model_rows if r.get("status", "completed") == "completed"]
        provider_errors = sum(1 for r in model_rows if r.get("status") == "provider_error")
        runner_errors = sum(1 for r in model_rows if r.get("status") == "runner_error")
        model_output_errors = sum(1 for r in completed_rows if r.get("model_output_error"))
        passed_runs = sum(1 for r in completed_rows if r.get("passed") is True)
        task_pass_rates = []
        for task in selected:
            task_rows = [r for r in model_rows if r["task_id"] == task.id]
            valid_rows = [r for r in task_rows if r.get("status", "completed") == "completed"]
            passed = sum(1 for r in valid_rows if r.get("passed") is True)
            valid_count = len(valid_rows)
            task_pass_rates.append({
                "task_id": task.id,
                "passed_trials": passed,
                "trials": valid_count,
                "attempted_trials": len(task_rows),
                "completion_rate": (valid_count / len(task_rows)) if task_rows else None,
                "provider_errors": sum(1 for r in task_rows if r.get("status") == "provider_error"),
                "runner_errors": sum(1 for r in task_rows if r.get("status") == "runner_error"),
                "model_output_errors": sum(1 for r in valid_rows if r.get("model_output_error")),
                "pass_rate": (passed / valid_count) if valid_count else None,
                "pass_at_k": (1.0 if passed else 0.0) if valid_count else None,
                "pass_power_k": (1.0 if passed == repeats else 0.0) if valid_count == repeats else None,
            })
        evaluated_tasks = [row for row in task_pass_rates if row["trials"] > 0]
        fully_repeated = [row for row in task_pass_rates if row["trials"] == repeats]
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
            (row.get("task_id"), row.get("trial"))
            for row, _incident in incident_rows
        }
        all_usage = [u for r in model_rows for u in r.get("usage", [])]
        served_models = sorted({u["served_model"] for u in all_usage if u.get("served_model")})
        unreported_model_calls = sum(1 for u in all_usage if not u.get("served_model"))
        summaries.append({
            "model": model,
            "served_models": served_models,
            "mixed_model_route": len(served_models) > 1,
            "unreported_served_model_calls": unreported_model_calls,
            "passed_trials": passed_runs,
            "completed_trials": len(completed_rows),
            "attempted_trials": len(model_rows),
            "total_trials": len(model_rows),
            "provider_errors": provider_errors,
            "runner_errors": runner_errors,
            "model_output_errors": model_output_errors,
            "pass_rate": passed_runs / len(completed_rows) if completed_rows else None,
            "trial_completion_rate": len(completed_rows) / len(model_rows) if model_rows else None,
            "evaluated_task_count": len(evaluated_tasks),
            "task_evaluation_coverage": len(evaluated_tasks) / len(selected) if selected else None,
            "fully_repeated_task_count": len(fully_repeated),
            "root_incident_count": len(incident_rows),
            "trials_with_root_incidents": len(trials_with_incidents),
            "root_incidents_by_type": dict(sorted(incident_type_counts.items())),
            "pass_at_k": (sum(1 for row in evaluated_tasks if row["passed_trials"] > 0) / len(evaluated_tasks)) if evaluated_tasks else None,
            "pass_power_k": (sum(1 for row in fully_repeated if row["passed_trials"] == repeats) / len(fully_repeated)) if len(fully_repeated) == len(selected) and selected else None,
            "per_task": task_pass_rates,
            "total_elapsed_ms": sum(r["elapsed_ms"] for r in model_rows),
            "usage_cost_usd": sum((u.get("cost") or 0) for u in all_usage)
                if all(u.get("cost") is not None for u in all_usage) else (0 if not all_usage else None),
        })
    return {
        "benchmark": "The Last Yes",
        "version": "0.1.9",
        "models": models,
        "repeats": repeats,
        "temperature": temperature,
        "task_count": len(selected),
        "turn_count": sum(len(t.turns) for t in selected),
        "summaries": summaries,
        "results": results,
    }
