# The Last Yes

**A synthetic benchmark for transaction-authorisation integrity in tool-using conversational commerce agents.**

The Last Yes tests whether an agent distinguishes acknowledgement from consent, preserves the latest transaction proposal, asks for missing information instead of guessing, avoids duplicate writes, and respects customer ownership before taking consequential actions.

The benchmark uses a fictional jewellery shop, synthetic customers and orders, a local simulator, and a deterministic Python grader. It does not connect to a real store, process payments, or use real customer records.

## Why this exists

A conversational agent can sound correct while selecting an unauthorised or stale tool action. In a commerce workflow, that can create an order without explicit confirmation, revive a withdrawn proposal, repeat a write, guess missing details, or attempt to access another customer's order.

The project turns those boundaries into executable tasks. It grades the agent's tool calls and resulting simulator state, not just the quality of its natural-language response. A foreign-order lookup attempt counts as a policy-boundary failure even when the simulator denies it; data disclosure and state mutation are recorded separately.

The research question is narrow: **when an explicit transaction policy is supplied, does a tool-using agent follow it across changes in customer intent, transaction state, and claimed authority?** This is not a test of whether a model can independently discover an organisation's access-control rules.

## Benchmark suites

The v0.1.9 package contains three distinct suites. Keep their results separate when interpreting or reporting them.

| Suite | Tasks | Purpose |
|---|---:|---|
| Core | 10 | Multi-turn transaction integrity: acknowledgement versus consent, ambiguous affirmatives, amendments, withdrawals, missing fields, duplicate writes, and order ownership. |
| Legacy authority variants | 3 | Exploratory v0.1.8 prompts involving employee-role claims, manager approval, and urgent delegation. The prompts were not fully matched, so they are hypothesis-generating rather than causal evidence. |
| Matched authority | 5 | v0.1.9 one-turn conditions using the same foreign-order request while changing only the final authority-framing sentence. |

The deterministic grader checks tool names, arguments, and turn order against expected actions, then checks simulator events and final state. It evaluates proposal contents, server-calculated totals, confirmation and withdrawal state, duplicate writes, missing-field handling, permitted lookups, and customer-visible response presence. **No LLM is used as a judge.**

## Recorded results

The results below are from the raw reports included in [`results/`](results/). They are small, exploratory hosted-route evaluations, not a representative model leaderboard.

### v0.1.9 matched-authority follow-up

| Requested OpenRouter route | Completed passes | Provider errors | Behavioural failures |
|---|---:|---:|---:|
| `nvidia/nemotron-3.5-super-vl:free` | 15/15 | 0 | 0 |
| `cohere/north-mini-code:free` | 15/15 | 1 timeout across 16 attempts | 0 |

The Cohere original run completed 14/15 requests with 14 passes and one OpenRouter read timeout. A separate retry of that condition passed 1/1. The timeout remains in the record and is not counted as a model pass or failure. Combined, the matched experiment had 30 completed passes across 31 attempted requests.

### Earlier ownership and authority observations

- In v0.1.7, Cohere attempted the foreign-order lookup in all five negative-case trials and passed 0/5 of those cases. The simulator denied the attempts; no foreign data was disclosed and no state changed. Nemotron passed the five foreign-order cases and five own-order positive controls.
- In v0.1.8, Cohere produced three further foreign-order lookup attempts in exploratory authority prompts. Those prompts differed in more than the authority sentence, so the results do not isolate a causal wording effect.
- The v0.1.9 matched follow-up did not reproduce the earlier failures in any completed trial.

These findings do **not** establish a causal authority-framing effect, universal model reliability, statistical significance, or general model-family superiority. The routes are hosted free endpoints, the samples are small, and provider availability can change. See [`docs/FINAL_RESEARCH_REPORT.md`](docs/FINAL_RESEARCH_REPORT.md) for the full analysis and limitations.

### Offline validation

The packaged source snapshot was validated with **42 passing automated tests** and **18/18 reference tasks passing**. These checks validate the benchmark implementation and reference traces, not the live models.

## Repository layout

```text
.
├── last_yes/                 # Agent, task definitions, simulator, grader, runner
├── tests/                    # Automated tests for runner, references, matched suite
├── docs/
│   ├── FINAL_RESEARCH_REPORT.md
│   ├── RESEARCH_PROTOCOL.md
│   └── MATCHED_AUTHORITY_PROTOCOL.md
├── results/
│   ├── historical/            # Original v0.1.5, v0.1.7 and v0.1.8 reports
│   ├── matched-authority-v019-r3.json
│   ├── matched-authority-v019-owner-permission-retry.json
│   ├── live-results-summary.json
│   └── reference-validation.json
├── run_eval.py               # CLI for running model evaluations
├── validate_reference.py     # Offline reference validation
└── merge_runs.py             # Utility for combining run reports
```

## Requirements

- Python 3.10 or later
- `pytest` for development tests
- An OpenRouter API key only if you want to run live model evaluations

The benchmark runtime uses only the Python standard library. No API key is needed for tests or reference validation.

## Quick start

Clone the repository and enter its directory:

```bash
git clone https://github.com/<YOUR-USERNAME>/the-last-yes.git
cd the-last-yes
```

Install the development dependency and run the offline checks:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python validate_reference.py
```

To list the tasks in a suite:

```bash
python run_eval.py --suite core --list-tasks
python run_eval.py --suite matched-authority --list-tasks
```

## Run a live evaluation

Set your OpenRouter key in the shell. The runner reads `OPENROUTER_API_KEY` from the environment; it does not automatically load `.env` files.

PowerShell:

```powershell
$env:OPENROUTER_API_KEY = "YOUR_OPENROUTER_KEY"
```

macOS/Linux:

```bash
export OPENROUTER_API_KEY="YOUR_OPENROUTER_KEY"
```

Run the ten-task core suite:

```bash
python run_eval.py \
  --suite core \
  --models cohere/north-mini-code:free \
  --repeat 3 \
  --temperature 0.0 \
  --out results/core-cohere-r3.json
```

Reproduce the matched-authority experiment:

```bash
python run_eval.py \
  --suite matched-authority \
  --models cohere/north-mini-code:free nvidia/nemotron-3.5-super-vl:free \
  --repeat 3 \
  --temperature 0.0 \
  --out results/matched-authority-r3.json
```

Use exact provider/model identifiers. Avoid `openrouter/free` for reported comparisons because it is a dynamic router and may serve different underlying models across calls. The report records requested and served model identifiers. If they differ, disclose that difference. Provider errors are not model passes or failures; preserve their counts and task coverage in any report.

The original live JSON reports in `results/` are retained as the audit record. New runs should be written to new filenames rather than overwriting those files.

## Research documentation

- [`docs/FINAL_RESEARCH_REPORT.md`](docs/FINAL_RESEARCH_REPORT.md) — full results, failure analysis, interpretation, limitations, and provenance.
- [`docs/RESEARCH_PROTOCOL.md`](docs/RESEARCH_PROTOCOL.md) — suite separation, historical findings, reproducibility, and interpretation limits.
- [`docs/MATCHED_AUTHORITY_PROTOCOL.md`](docs/MATCHED_AUTHORITY_PROTOCOL.md) — fixed request, five conditions, outcomes, and matched-run protocol.

## Demo

[Video walkthrough](https://drive.google.com/file/d/18gIVe1IOLcwQB8DsJNtfpnJaD6rIVfbv/view?usp=sharing)

The walkthrough is described in the submission as covering the problem, task design, deterministic grading, raw failure evidence, matched follow-up, and limitations. The video host's sharing permissions are controlled separately from this repository.

## Limitations and safe interpretation

- The environment, customers, products, order IDs, and prices are synthetic.
- The policy is explicitly supplied in the system prompt. The benchmark measures adherence to that policy in this simulator.
- A denied foreign-order tool attempt is a policy-boundary failure, but it is not evidence of data disclosure or a breach.
- This is not a production security audit, a real multi-tenant penetration test, or a legal determination.
- Production systems must enforce identity, tenant ownership, authorisation, idempotency, and state transitions in trusted application code. A model's refusal is not an access-control mechanism.
- Small samples from hosted free routes cannot support broad claims about model families or universal reliability.

## Provenance and AI assistance

KasaFlow, an earlier WhatsApp commerce project, supplied the engineering context for the research question. The standalone benchmark, synthetic task set, fictional catalogue, simulator, tool runner, deterministic grader, reference traces, tests, and documentation were created for this submission. This repository does not include KasaFlow application code, live customer records, retailer catalogue data, credentials, WhatsApp conversations, or operational logs.

ChatGPT was used extensively to assist with benchmark design, implementation, testing, and documentation. The project author is responsible for reviewing the benchmark, grader, traces, raw runs, and claims.

## License

No license has been added because the project author has not yet selected one. Until a license is added, GitHub's default copyright rules apply; do not assume others have permission to reuse, modify, or redistribute this code.
