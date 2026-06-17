# Retrieval / Support Eval Set

This folder contains lightweight evaluation data for Docstore retrieval and support-answer quality.

## Goals

We use these evals to measure whether changes improve or regress:

- grounded answer quality
- source usefulness
- no-answer / handoff correctness
- capability routing (knowledge vs shipping vs fallback)

## Eval record format

Each line in `support_knowledge_eval.jsonl` is a JSON object with fields like:

- `id` — stable eval id
- `workspace_slug` — target workspace
- `question` — user/support question
- `expected_mode` — `knowledge`, `shipping`, or `no_answer`
- `expected_answer_themes` — concepts the answer should contain
- `expected_source_hints` — expected source docs/sections
- `must_not_claim` — things the answer must not invent
- `tags` — optional category labels

## Why this exists

Docstore should improve based on real support questions, not vibes.
Before changing chunking, ranking, or answer assembly, capture a baseline.
After changes, compare outcomes against the same eval set.

## Suggested review dimensions

For each eval, review:

- Was the selected mode correct?
- Was the answer grounded and useful?
- Were the sources relevant?
- Did the system avoid false confidence?
- If no answer existed, did it fall back honestly?

## Notes

These evals should grow over time.
Whenever a real-world question fails in production, add a version of it here.

## Files

- `support_knowledge_eval.jsonl` — starter mixed eval set
- `tenant_question_bank_template.jsonl` — template for building a more realistic tenant/workspace-specific eval bank
