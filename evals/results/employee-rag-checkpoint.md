# Employee Workspace RAG Checkpoint

_Date:_ 2026-06-18

## Baseline

Initial employee workspace eval run:

```bash
python manage.py run_support_evals \
  --file evals/employee_workspace_eval.jsonl \
  --format json \
  --save evals/results/employee-baseline.json
```

Result:
- 10 evals
- mode matches: 7/10
- handoff matches: 7/10

## Main findings from baseline

- The employee workspace was not broadly broken.
- Biggest weakness was **no-answer detection / orchestration**.
- One likely real retrieval issue appeared around **PTO approval**.
- Two misses were basically unsupported questions being mislabeled as `knowledge`.

## Tooling added

### Retrieval inspection command

Added management command:

```bash
python manage.py inspect_retrieval \
  --file evals/employee_workspace_eval.jsonl \
  --save evals/results/employee-retrieval-inspection.json
```

Purpose:
- inspect corpus presence
- inspect exact-query and variant-query retrieval
- capture hybrid / vector / metadata / question / lexical retrieval views
- save JSON for failed eval analysis

Commit:
- `69de4f3` — Add retrieval inspection command for eval debugging

## Retrieval inspection findings

### PTO approval
- Handbook contained nearby leave / approval language.
- Did **not** contain a clean explicit sentence that “PTO requires manager approval.”
- Retrieval improved with query variants like:
  - `paid time off approval`
  - `does paid time off require supervisor approval`
- This looked like a **terminology mismatch / adjacent-policy retrieval** case.

### Coworking reimbursement / home office furniture
- Behaved like true **no-answer** cases.
- Retrieval mostly surfaced adjacent reimbursement noise, not grounded policy answers.

## Retrieval changes

Implemented a cautious general retrieval improvement:
- broader general term expansion
- slight scoring rebalance toward question-style matches

Examples:
- manager ↔ supervisor
- PTO / leave / vacation / paid time off
- reimbursement / expense
- remote / telework
- handbook / policy

Commit:
- `acc02df` — Improve general retrieval term expansion and scoring

Effect:
- original employee eval improved from 7/10 to 8/10

## No-answer handling changes

### Phrase-based tightening
Commit:
- `4357e0c` — Tighten no-answer detection for support responses

Effect:
- original employee eval improved from 8/10 to 9/10

### Expanded eval set
Expanded employee eval file from 10 to 17 questions.

Added cases for:
- parking reimbursement
- moving / relocation expenses
- optional payroll deductions
- doctor’s note for sick leave
- unapproved leave
- hybrid schedule
- dental waiting period

Commit:
- `ee9abf9` — Refine no-answer detection and expand employee evals

### Pattern-based no-answer detection
Commit:
- `cdf9641` — Make support no-answer detection pattern-based

This caught more unsupported cases but became too aggressive and regressed overall eval score.

### Balanced no-answer detection with retrieval evidence
Final tuned version:
- split no-answer language into **strong** vs **soft** signals
- only hand off soft no-answer responses when retrieval evidence is weak
- use top retrieved `blended_score` as evidence signal

Commit:
- `b3555d0` — Balance no-answer detection with retrieval evidence

## Eval policy decision

Chose **strict mode** for the employee eval set:

> If the docs do not directly answer the question, expected mode = `no_answer`.

Under this policy, relabeled:
- `employee_pto_approval_001` → `no_answer`
- `employee_direct_deposit_001` → `no_answer`
- `employee_remote_work_001` → `no_answer`

Commit:
- `94c0b22` — Align employee evals with strict no-answer grading

## Current best result

Strict-mode expanded employee eval run:
- 17 evals
- mode matches: 15/17
- handoff matches: 15/17

Saved report:
- `evals/results/employee-expanded-evals-strict-mode.json`

## Remaining misses

### 1) PTO approval
Expected:
- `no_answer`

Actual:
- `knowledge`

Current behavior:
- system gives a careful negative answer using adjacent leave policy
- under strict grading, this should still be a no-answer / handoff case

### 2) Hybrid schedule
Expected:
- `no_answer`

Actual:
- `knowledge`

Current behavior:
- system uses flexible scheduling language as adjacent evidence
- under strict grading, this should still be a no-answer / handoff case

## Recommended next step

If continuing from here, the next targeted polish is:
- treat phrasing like:
  - `does not explicitly state`
  - `does not specify`
  - `no evidence that X specifically`
  as **soft no-answer** language
- then hand off when the evidence is only adjacent / indirect

That should likely address the two remaining strict-mode misses:
- PTO approval
- hybrid schedule

## Current conclusion

This is a solid checkpoint.

Progress summary:
- baseline: 7/10 on original 10-question set
- improved: 9/10 on original set
- expanded strict-mode set: 15/17

At this point the remaining work is edge-case classification polish, not broad RAG failure.
