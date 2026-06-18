# ProLiant + Proxi-Web Checkpoint

_Date:_ 2026-06-18

## Problem

The question:

> What are ProLiant's paid holidays?

was present in the handbook, but Proxi-Web was failing to answer it correctly.

Observed bad behavior:
- claimed the handbook did not list the holidays
- sometimes referenced nearby eligibility/observation chunks instead of the actual holiday list
- Proxi-Web behavior diverged from shell/eval testing because it was not using the same orchestration path as other chat/support surfaces

## Root causes discovered

### 1) Handbook structure metadata was initially weak
The relevant holiday chunk existed, but the extracted chunk structure was poor due to PDF text-layer artifacts / glyph weirdness and flattened inline bullets.

Key chunk:
- ProLiant handbook chunk `205`
- contains section `6-3. Holidays`
- contains bullet list of named holidays

Fixes made:
- improved inline heading parsing for patterns like `6-3. Holidays`
- improved inline bullet list extraction for flattened `• item • item` text
- normalized structure-analysis text for PDF artifacts (unicode normalization, punctuation cleanup, common ligature/glyph cleanup)

Relevant commits in this area:
- `6752d70` — Improve chunk structure extraction for inline lists
- `5e9dccf` — Tighten inline heading and list parsing
- `060c047` — Normalize structure analysis for PDF text artifacts

After reingest, chunk `205` correctly showed:
- `dominant_heading = "6-3. Holidays"`
- `has_list = true`
- `list_count = 7`

### 2) Retrieval pool was good enough, but answer context cutoff was too narrow
After metadata was fixed, chunk `205` still ranked just below the top answer cutoff.

Key finding:
- chunk `205` was present in broader retrieval / blended results
- but often not in the top 5 chunks used for answer generation
- when the answer path used a wider `top_k` (8/10/12), the holiday question answered correctly

Relevant commits:
- `ed9a906` — Boost list chunks for list-seeking questions
- `f5fd48c` — Increase default retrieval context for answers

Practical result:
- a modestly wider answer context (`top_k=8`) was enough for the model to see the actual holiday list chunk and answer correctly

### 3) Proxi-Web was not using the shared support orchestration path
This was the biggest behavioral mismatch.

Proxi-Web originally used a custom path in `control/views.py`:
- `retrieve_chunks(top_k=5)`
- `build_context_blocks(...)`
- `answer_with_general_context(...)`

Other surfaces used shared orchestration via:
- `handle_support_request(...)`

This caused drift in:
- retrieval parameters
- no-answer behavior
- future fixes landing in one path but not the other

Relevant commits:
- `3a2a66d` — Align support retrieval context with answer defaults
- `5d03f06` — Route Proxi-Web through shared support orchestration

After `5d03f06`, Proxi-Web began using the same shared orchestration layer as the other support/chat surfaces.

## Final successful behavior

After:
- structure metadata fixes
- wider answer context
- Proxi-Web orchestration alignment

Proxi-Web correctly answered:

- New Year's Day
- Memorial Day
- Independence Day
- Labor Day
- Thanksgiving Day
- Day after Thanksgiving
- Christmas Day

and correctly included the holiday observation rule:
- Saturday holidays observed on Friday
- Sunday holidays observed on Monday

## Important implementation notes

### Temporary debugging changes removed
Temporary debug scaffolding and temporary ingest chunk-cap increase were removed after debugging.

Cleanup commit:
- `9f6c745` — Remove temporary ingestion debugging scaffolding

### Durable changes that remain
The durable changes that should remain live are:
- normalized structure analysis for PDF text artifacts
- improved inline heading/list parsing
- wider default retrieval context for answer generation (`top_k=8`)
- Proxi-Web routed through shared support orchestration

## Architectural takeaway

Proxi-Web should not maintain a custom answer-generation pipeline when other surfaces use shared support orchestration.

Shared orchestration reduces drift in:
- retrieval parameters
- no-answer behavior
- future bug fixes
- eval alignment

If chat-history-aware behavior is needed later, extend shared orchestration to accept optional history rather than reintroducing a separate Proxi-Web answer stack.

## Current state

As of this checkpoint:
- ProLiant paid-holidays question works correctly in Proxi-Web
- Proxi-Web now shares the same orchestration layer as the other support/chat surfaces
- employee strict-mode eval remained at 15/17 after the wider answer-context change
- Proliant eval was previously clean aside from the holiday issue, which is now resolved in live behavior
