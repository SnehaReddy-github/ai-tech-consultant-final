# EVALUATIONS

## 1. Verified Test Results

The following results were reported from local test runs.

| Task | Evaluation | Result |
|---|---|---|
| Task 1 — Knowledge Brain | Automated tests | 43 passed |
| Task 2 — Inbox Agent | Automated tests | 25 passed |
| Task 2 — Inbox Agent | TypeScript type-check | Passed |
| Task 2 — Inbox Agent | Sample email dataset | 50 emails, 50 unique IDs, 5 categories |
| Task 3 — Meeting to Scope | Automated tests | 5 passed |

**Total reported automated tests: 73 passed.** This total combines the reported results from all three tasks; it does not establish complete end-to-end integration.

## 2. Task 1 — Knowledge Brain

### Evaluation plan

Evaluate at least 20 support questions covering:

- Questions answerable from the knowledge base.
- Ambiguous and unsupported questions.
- Updated or removed articles.
- Image/OCR-based questions.
- Broken sources and unavailable services.

### Metrics to record

- Answer correctness and grounding in cited sources.
- Citation validity and accessibility.
- Handling of unsupported questions and creation of human-review tasks.
- Response latency.

**Current status:** 43 automated tests passed, as reported locally. Systematic answer-quality measurements, citation-quality results, and latency measurements have not yet been recorded.

## 3. Task 2 — Inbox Agent

### Dataset verification

The sample dataset is located at `task2-inbox-agent/data/sample-emails.json`.

Verified locally:
- Total email records: 50.
- Unique email IDs: 50.
- Categories present: support, pricing, sales, meeting, and general.

The dataset count and unique IDs are verified. This does not, by itself, establish that all required email scenarios are covered or that an independent held-out test set exists.

### Evaluation plan

Test at least 50 realistic emails and evaluate an unseen set separately. Include billing questions, product inquiries, complaints, spam, urgent requests, ambiguous messages, and duplicate emails.

Measure:
- Classification accuracy.
- Draft acceptance and edit rates.
- Unsafe automatic-send rate.
- Duplicate handling.
- Feedback-learning behavior.
- Enforcement of the 20-consecutive-unchanged-drafts rule.
- Revocation of automatic sending after quality degradation.
- Human override and approval behavior.

**Current status:** 25 automated tests passed and TypeScript type-checking passed, as reported locally. The 50-email dataset is verified. Held-out-set quality and systematic behavioral metrics remain unmeasured.

## 4. Task 3 — Meeting to Scope

### Evaluation plan

Evaluate at least 20 meeting transcripts covering vague requirements, explicit deliverables, conflicting requests, missing deadlines, estimates, existing-feature questions, integrations, follow-up changes, and Task 1 outages.

Measure:
- Requirement extraction completeness.
- Usefulness of clarification questions.
- Task and deliverable completeness.
- Estimate error against human estimates.
- Correct use of Task 1 evidence.
- Preservation of human approval before client-facing proposals.
- Correct identification of changed, new, and out-of-scope requests.

**Current status:** 5 automated tests passed in the reported local run. The required 20-transcript evaluation and systematic scope-quality measurements have not yet been verified.

## 5. Model and System Evaluation

Live Claude API performance has not been measured because API access was unavailable in the reported setup.

| Metric | Current result |
|---|---|
| Task 1 automated tests | 43 passed |
| Task 2 automated tests | 25 passed |
| Task 2 TypeScript type-check | Passed |
| Task 2 sample dataset | 50 records; 50 unique IDs |
| Task 3 automated tests | 5 passed |
| Task 1 systematic answer quality | Not measured |
| Task 2 held-out-set quality | Not measured |
| Task 3 scope quality | Not measured |
| Live Claude latency and cost | Not measured |
| End-to-end integration tests | Pending verification |
| Model comparison results | Pending evaluation |

## 6. Limitations and Next Steps

1. Build and run the required evaluation cases for each task.
2. Separate development examples from held-out evaluation data.
3. Record actual correctness, latency, and human-review measurements.
4. Compare model configurations using the same evaluation cases, where API access permits.
5. Verify the integration of all three tasks and preserve human approval for external actions.
6. Update this document only with results reproduced locally.

**Reporting policy:** Automated unit-test results do not establish production readiness or complete assignment compliance. No unmeasured accuracy, latency, cost, or approval metrics are claimed.
