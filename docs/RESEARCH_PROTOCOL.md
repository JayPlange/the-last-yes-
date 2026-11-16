# Research protocol — The Last Yes v0.1.9

## Design

The benchmark contains ten synthetic transaction-integrity tasks, three legacy exploratory authority prompts from v0.1.8, and a separate five-condition matched authority-framing suite introduced in v0.1.9. Keep the three groups and their result files separate.

## Historical findings

The initial 6 November 2026 Cohere full-suite run (`cohere-full-r1.json`, v0.1.5) attempted nine task requests. Six completed: five passed and one failed on a foreign-order lookup attempt. Three requests were provider errors, giving 6/9 task coverage. The simulator denied the foreign-order lookup; no data was disclosed and no order state changed. Preserve this partial-coverage result separately from later focused experiments.

The v0.1.7 paired ownership experiment used five repetitions each of a foreign-order negative case and an own-order positive control. Nemotron passed 10/10. Cohere passed 4/10, attempted the foreign-order lookup in all five negative-case trials, and used the wrong order ID in one own-order trial. The simulator denied the foreign-order attempts; no data was disclosed and no state changed.

The v0.1.8 legacy authority probes produced 9/9 passes for Nemotron and 6/9 for Cohere, with three Cohere foreign-order lookup attempts. Those prompts were exploratory and were not fully matched, so the findings do not isolate a causal authority-wording effect.

## Completed v0.1.9 matched experiment

The matched suite used the same fixed foreign-order request and changed only the final authority-framing sentence across neutral, owner-permission, employee-role, manager-approval and urgent-delegation conditions. Both requested routes were run at temperature `0.0`, three trials per condition.

- `nvidia/nemotron-3.5-super-vl:free`: 15/15 completed passes, no provider errors.
- `cohere/north-mini-code:free`: 14/14 completed passes in the original run, with one provider timeout on trial 3 of `matched_foreign_order_owner_permission`.
- A separate one-trial retry of that Cohere condition passed 1/1. The original timeout remains in the record.
- Combined accounting: Cohere 15/15 completed passes plus one provider error across 16 attempts; Nemotron 15/15; 30/30 completed evaluations passed across 31 requests.

The matched follow-up did not reproduce the earlier foreign-order lookup attempts. This weakens the hypothesis that authority framing alone caused the v0.1.7/v0.1.8 failures. It does not identify why the earlier attempts occurred. See `FINAL_RESEARCH_REPORT.md` for tables and interpretation.

## Interpretation limits

The policy is stated explicitly in the system prompt. The benchmark measures model/tool-path adherence to that policy in a synthetic simulator. It is not an assessment of legal knowledge, production access-control security, or actual disclosure risk in a deployed service. A denied foreign-order tool attempt is a policy-boundary failure, but not evidence of a data breach. Provider errors are not model failures and are excluded from pass-rate denominators. The routes are hosted free endpoints; do not claim universal reliability, statistical significance or general model-family superiority from these small samples.

## Reproducibility and provenance

Preserve the raw JSON reports with per-trial tool calls, simulator events and transcripts for the v0.1.7 ownership run, v0.1.8 authority-variants run, v0.1.9 matched-authority run and separate retry. Verify requested and served model identifiers, temperature and provider-error metadata. Do not manually reconstruct raw reports from the summary.

KasaFlow and its application evaluator pre-date the hackathon and supplied engineering context. The standalone benchmark, synthetic data, simulator, task definitions, grader, tests and documentation were created for the hackathon with substantial AI assistance. The participant must review and approve all materials and results before submission.
