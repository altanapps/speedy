# Eval — selection→market labeled set

The labeled corpus used to measure retrieval quality. Each row pairs a
realistic highlight (with surrounding context) against the Polymarket
market a human reviewer would expect Speedy to return.

Top-1 accuracy on this set is the only honest measure of whether the
retriever works.

## Status

Empty placeholder. The harness + seed fixtures are tracked in
[issue #10](https://github.com/altanapps/speedy/issues/10).

If you've used Speedy and noticed cases where the search picked a
clearly-wrong market, those failures are exactly what this corpus
should capture. Open an issue or drop them in the thread.

## Intended layout

```
eval/
  fixtures/        # raw highlights with context + window/app metadata
  labels.jsonl     # {fixture_id, expected_market_id, notes}
  reports/         # generated accuracy reports per commit
```

## Why this exists

Without measurement on representative inputs, every retrieval change is
opinion. Threshold tuning, prompt edits, model swaps — none of them are
"better" until they move a number on this set.

Aim: ~30–50 hand-labeled examples covering short ambiguous queries
(*"Powell"*), long sentences with contextual signals, and categories
across the active market set (macro, politics, crypto, sports). The
hardest-to-label cases — phrasings that don't lexically match the
market question — are the ones that matter most.
