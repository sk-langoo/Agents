# Ten manual scenarios for the current local workbooks

These scenarios use the **current synthetic spreadsheets**. Run each case
first with `python demo.py --customer "NAME" --quarter YYYY-QN` for free. That
shows the deterministic baseline. To test the language model, run `python
agent.py` with your own API key and ask the matching question; that live run
may cost money. Check the agent's structured answer against the baseline.

For a financial question, look for the `calculate_rebate_deterministically`
tool call. A missing call is a failure even if the final number looks right.
The model's explanation should not invent evidence or turn unknown values
into zero.

| # | Customer | Quarter | What to look for in the deterministic result |
| ---: | --- | --- | --- |
| 1 | Acme Retail | 2026-Q2 | `completed`; `THRESHOLD_NOT_MET`; expected rebate is zero. |
| 2 | Summit Apparel | 2026-Q2 | `review_required`; `CONFLICTING_CONTROLLING_AGREEMENTS`; do not choose an amendment. |
| 3 | Granite Motors | 2026-Q3 | `review_required`; `DUPLICATE_TRANSACTION_ID`; do not double-count. |
| 4 | Northstar Energy | 2026-Q2 | `review_required`; `AMBIGUOUS_AGREEMENT`; do not interpret vague terms as fact. |
| 5 | Redwood Schools | 2026-Q2 | `review_required`; agreement is pending renewal. |
| 6 | Frontier Labs | 2026-Q3 | `review_required`; paid rate and agreement reference do not match the controlling amendment. |
| 7 | Quartz Manufacturing | 2026-Q2 | `review_required`; transaction data-quality flag. |
| 8 | Valley Aviation | 2026-Q3 | `review_required`; suspended agreement. |
| 9 | Harbor Hotels | 2026-Q4 | `review_required`; duplicate transaction ID. |
| 10 | Falcon Equipment | 2026-Q4 | `completed`; threshold missed; approved payment exceeds expected rebate. |

Example free run:

```bash
python demo.py --customer "Granite Motors" --quarter 2026-Q3
```

Example live prompt for the agent:

```text
Investigate Granite Motors' rebate for 2026-Q3. Is the payment supported by the agreement and transactions?
```

The exact wording of a conclusion may vary. Focus on tool use, evidence,
numbers, review status, and whether the next action is sensible.
