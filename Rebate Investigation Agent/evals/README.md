# Rebate Agent Evaluation Dataset

`rebate_investigations.jsonl` contains 30 synthetic investigations. JSONL means
that every line is one complete JSON case. This format is easy for Python to
process and can later be transformed for an evaluation platform.

The dataset is self-contained. Each case has its own source evidence, so it
does not alter or depend on the demo spreadsheets. The current prototype
cannot execute every case yet because its three tools do not expose agreement
amendments, transaction control totals, approval policies, or detailed contract
language. Those cases intentionally describe the behavior a production agent
must eventually support.

## Dataset structure

- `case_id`: Stable identifier for the case.
- `category`: Primary failure mode or business scenario.
- `title`: Short human-readable name.
- `input`: Customer, quarter, and user question sent to the agent.
- `source_data`: Synthetic agreements, transactions, payments, and any relevant
  control evidence.
- `expected.status`: Expected structured result status.
- `expected.human_review`: Whether the case must be escalated.
- `expected.expected_tool_sets`: Exact acceptable sequences of tool names.
- `expected.eligible_sales`, `threshold`, `rebate_rate`, `expected_rebate`,
  `amount_paid`, and `variance`: Exact expected financial results. `null` means
  the result cannot be established safely.
- `expected.decision`: The essential conclusion, not wording that must be
  copied verbatim.
- `expected.evidence_ids`: Records that must support the conclusion.
- `expected.must_not_claim`: Claims that make the result fail.

Money and rates are strings in the dataset so decimal precision is preserved.

## Coverage

| Category | Cases |
| --- | ---: |
| Eligible rebate | 3 |
| Threshold missed | 3 |
| Excluded products | 3 |
| Contract date mismatch | 2 |
| Missing transactions | 2 |
| Duplicate transactions | 2 |
| Incorrect rebate rate | 2 |
| Incorrect payment | 3 |
| Ambiguous language | 2 |
| Conflicting amendments | 2 |
| Missing agreement | 2 |
| Human review | 4 |
| **Total** | **30** |

Several cases could reasonably have more than one category. The primary
category keeps reporting simple; tags can be added later if multi-label
analysis becomes useful.

## Metrics

### Task success

**Question:** Did the agent resolve the case correctly?

Per case, score `1` only when the required tools, evidence, calculations,
decision, and escalation behavior all pass. Otherwise score `0`.

```text
task success rate = successful cases / all cases
```

This is the strict end-to-end metric. It can be lower than the individual
component metrics because one failed component fails the task.

### Tool-selection accuracy

**Question:** Did the agent use the right systems?

Compare the observed ordered tool list with one of the case's
`expected_tool_sets`. Use exact-match accuracy for this initial dataset. Later,
separate tool precision and recall if several optional tools are introduced.

```text
tool-selection accuracy = exact tool matches / all cases
```

### Evidence correctness

**Question:** Did the conclusion follow the source data?

Score `1` when every material conclusion is supported by the listed source
records, all required `evidence_ids` were considered, and contradictory source
evidence was acknowledged. Otherwise score `0`.

```text
evidence correctness = evidence-grounded cases / all cases
```

This requires a rule-based check for cited IDs plus human or model grading for
the meaning of the conclusion.

### Calculation accuracy

**Question:** Did it compute correctly?

Compare every non-null expected numeric field using decimal arithmetic. Use
exact equality after the defined currency rounding rule; do not use approximate
floating-point comparison for production financial evaluation.

```text
calculation accuracy = exact numeric fields / numeric fields expected
```

Also report strict case accuracy: the percentage of calculable cases where all
numeric fields are exact.

### Hallucination rate

**Question:** Did it invent facts?

A case hallucinates when the result asserts a material fact unsupported by
`source_data`, cites a nonexistent record, or makes a claim listed in
`must_not_claim`.

```text
hallucination rate = cases with at least one invented material fact / all cases
```

Lower is better. Report the raw count alongside the percentage.

### Escalation recall

**Question:** Did it catch cases requiring humans?

```text
escalation recall = correctly escalated review cases / all human-review cases
```

The denominator is cases where `expected.human_review` is `true`. Missing a
necessary escalation is a false negative.

### False escalation rate

**Question:** Did it unnecessarily involve humans?

```text
false escalation rate = incorrectly escalated auto-resolvable cases / all auto-resolvable cases
```

The denominator is cases where `expected.human_review` is `false`. Lower is
better.

### Latency

**Question:** Was it fast enough?

Record wall-clock milliseconds from immediately before the runner starts until
the structured result is available. Report median, p95, and p99 latency, plus
tool and model time separately when tracing is available.

Do not set a pass threshold until the product team defines an interactive
service-level objective and measures an initial baseline.

### Cost per task

**Question:** Is it economical?

Capture input tokens, cached input tokens, output tokens, model/tool charges,
and retry charges for each case.

```text
cost per task = total evaluated API and tool cost / completed tasks
```

Also report cost per successful task:

```text
cost per successful task = total evaluated cost / successful tasks
```

This prevents a cheap but inaccurate configuration from looking favorable.

## Recommended scorecard

For each run, save:

| Field | Purpose |
| --- | --- |
| Case ID | Join result to reference case |
| Model and version | Reproduce model configuration |
| Prompt version | Detect prompt regressions |
| Observed tools | Grade tool selection |
| Structured result | Grade facts and calculations |
| Evidence IDs used | Grade grounding |
| Human-review decision | Grade escalation behavior |
| Latency milliseconds | Measure user experience |
| Input/output/cached tokens | Explain cost |
| Estimated cost | Compare configurations |
| Error and retry count | Separate quality from reliability |

## How to use it now

Run the free structural validation:

```bash
python -m unittest discover -s tests -v
```

## Run the evaluation

The project now has `eval_runner.py`. It creates fresh, controlled versions of
the three tools for every case. Those tools can see only that case's embedded
evidence. The runner captures the structured answer, tool activity, token use,
latency, grader details, and aggregate metrics.

First validate the setup without making an API call:

```bash
python eval_runner.py --case RB-001 --dry-run
```

Then run one live case:

```bash
python eval_runner.py --case RB-001
```

Run several chosen cases by repeating `--case`:

```bash
python eval_runner.py --case RB-001 --case RB-004 --case RB-021
```

Run all 30 only after reviewing the small runs:

```bash
python eval_runner.py --all
```

`--all --limit 5` runs only the first five. Live runs use the OpenAI API and
therefore may incur cost. Result files are stored under `evals/results/`.

Cost remains `null` unless current model prices are supplied explicitly. This
avoids silently using a stale hard-coded price:

```bash
python eval_runner.py --case RB-001 \
  --input-cost-per-million INPUT_PRICE \
  --output-cost-per-million OUTPUT_PRICE
```

Replace the two placeholders with current USD prices per one million tokens.
