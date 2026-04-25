# Eval — selection→market labeled set

Holds the labeled evaluation corpus used to measure retrieval quality.

Each row pairs a realistic highlight (with surrounding context) against the Polymarket market a human reviewer would expect Speedy to return. Top-1 accuracy on this set is the only honest measure of whether the retriever works.

## Layout (TBD, set in PR 4 / PR 5)

```
eval/
  fixtures/        # raw highlights with context + window/app metadata
  labels.jsonl     # {fixture_id, expected_market_id, notes}
  reports/         # generated accuracy reports per commit
```

## Why this exists before any feature code

If we cannot measure retrieval quality on representative inputs, we cannot tell whether tuning the embedding model, prompt, or threshold actually helps. The eval set is the source of truth — every retrieval change ships with a delta against it.

Status: empty placeholder. PR 4 wires the schema and seeds the first ~50 fixtures.
