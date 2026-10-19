# EVALUATIONS

## Current verified results

- Task 1: 43 tests passed in the latest reported run.
- Task 2: 25 tests passed; TypeScript type-check completed without errors.
- Task 3: add the results of `python -m pytest task3-meeting-to-scope/tests -q`
  after running it locally. Do not report a pass until it succeeds.

## Evaluation plan

Evaluate each task on correctness, evidence grounding, safe failure behavior,
latency, and ease of human correction.

### Task 1 — Knowledge Brain

Use at least 20 questions from the support domain. Include answerable questions,
ambiguous questions, unsupported questions, changed articles, removed URLs,
image/OCR-based questions, and broken-source scenarios. Record whether the
answer is supported by its cited source, whether citations open correctly,
whether unsupported questions create review tasks, and response time.

### Task 2 — Inbox Agent

Use at least 50 realistic email examples, with a held-out unseen set. Include
billing, product questions, complaints, spam, urgent requests, and ambiguous
messages. Measure classification accuracy, draft acceptance/edit rate,
unsafe-send rate, duplicate handling, and feedback-learning behavior. Verify
the 20-consecutive-unchanged-drafts rule, quality degradation revocation, and
human override. Do not enable automatic sending based only on a small test set.

### Task 3 — Meeting to Scope

Create at least 20 evaluation transcripts, including vague requirements,
explicit deliverables, conflicting requests, missing deadlines, estimates,
existing-feature questions, integration requests, follow-up changes, and
Task 1 outage. Score extracted requirements, useful clarification questions,
task completeness, estimation error against human estimates, correct use of
Task 1 evidence, and whether approval gates are preserved.

## Results table

Fill this table with actual measurements before submission.

| Metric | Result |
|---|---|
| Task 1 tests | 43 passed (reported locally) |
| Task 2 tests | 25 passed (reported locally) |
| Task 2 type-check | Passed (reported locally) |
| Task 3 tests | Pending local execution |
| Task 1 answer quality | Not yet measured systematically |
| Task 2 unseen-set quality | Not yet measured systematically |
| Task 3 scope quality | Not yet measured systematically |
| Live Claude latency/cost | Not measured; API access unavailable |
| End-to-end tests | Pending |

Do not invent accuracy, latency, cost, or human-approval measurements.
