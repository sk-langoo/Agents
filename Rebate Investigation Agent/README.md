# Rebate Investigation Agent

A Python portfolio project that investigates synthetic customer rebates. The
OpenAI Agents SDK helps interpret a question, select read-only evidence tools,
and return a structured answer. A separate deterministic service applies
rebate rules and decimal arithmetic. The project runs locally; it does not
connect to a company system or make payments.

## Try it without an API key

Requires Python 3.11 or newer. From a fresh clone:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python demo.py
```

`demo.py` runs the spreadsheet-backed calculation service, not the language
model. It prints each major step in plain English and uses no API credits. Try
an exception case:

```bash
python demo.py --customer "Summit Apparel" --quarter 2026-Q2
```

The expected outcome is `review_required` because conflicting amendments are
present. The demo writes a local audit trail in `local_data/`; Git ignores it.

Run all free local tests:

```bash
python -m unittest discover -s tests -v
```

## Try the actual AI agent

This optional path calls the OpenAI API and may incur a charge. Use **your own**
API key—never commit it, paste it into a GitHub issue, or send it to the author.
Set `OPENAI_API_KEY` in your local terminal as described in the
[OpenAI developer quickstart](https://developers.openai.com/api/docs/quickstart),
then run:

```bash
python agent.py
```

Example question:

```text
Investigate Acme Retail's rebate for 2026-Q2. Was the correct amount paid?
```

The CLI shows tool activity and prints a structured JSON answer. You can also
use the ten current scenarios in [MANUAL_TEST_CASES.md](MANUAL_TEST_CASES.md).

## How it works

```text
Question → Agents SDK → read-only evidence tools → synthetic spreadsheets
                     ↘ deterministic calculation tool → rules and audit
                     → structured answer
```

- `agent.py` defines the agent, its four tools, and the result schema.
- `production/spreadsheet_provider.py` reads the three local workbooks and
  converts rows into typed agreements, transactions, and payments.
- `production/engine.py` applies versioned eligibility, threshold, rate,
  payment, and escalation rules with exact decimal arithmetic.
- `production/service.py` joins demo authorization, retrieval, calculation,
  metrics, and audit events.
- `rebate_agreements.xlsx`, `transactions.xlsx`, and `rebate_payments.xlsx`
  contain synthetic data, deliberate exceptions, and a data dictionary.
- `evals/` contains 30 synthetic investigations and an evaluation guide.
- `eval_runner.py` runs selected cases using isolated test tools, captures
  answers and tool activity, and computes evaluation metrics.
- `tests/` contains API-free unit tests.
- `PRODUCTION_READINESS_REQUIREMENTS.md` describes future enterprise gates.

An evaluation dry run is free:

```bash
python eval_runner.py --case RB-001 --dry-run
```

A live evaluation calls the API:

```bash
python eval_runner.py --case RB-001
```

See [evals/README.md](evals/README.md) for metrics and more options.

## Security and maturity

The workbooks contain invented businesses and transactions. The repository
does not include an API key. Local secrets, audit logs, eval outputs, backups,
build files, and virtual environments are excluded by `.gitignore`. Before
publishing changes, run:

```bash
python scripts/check_public_safety.py
```

The project is a **local learning prototype**, not a production financial
system. The CLI uses a simulated actor, its three evidence tools do not have
independent authorization, and the model is instructed—but not forced by
application code—to use the deterministic calculator. Financial outputs need
human verification. See [SECURITY.md](SECURITY.md) for the full boundary.
