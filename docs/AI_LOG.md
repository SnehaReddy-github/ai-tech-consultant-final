# AI LOG

This file records representative development prompts and a rejected approach.
Update it to match the actual prompts and decisions made during development.

## Representative prompts

1. Build a polite, resumable support-article crawler with bounded batches.
2. Improve retrieval so weak matches do not produce unsupported answers.
3. Create an inbox workflow with human review and conservative auto-send rules.
4. Convert meeting transcripts into draft tasks and ask clarifying questions.
5. Add tests for unavailable services, follow-up changes, and approval gates.

## Rejected approach

Rejected approach: return a confident custom-development recommendation when
the knowledge service cannot be reached.

Reason: without checking existing documentation, the system could recommend
work that is already supported by a documented feature, mislead a customer,
or create unnecessary scope. Task 3 instead marks the knowledge check as
unavailable and blocks the recommendation for human review.

## Model and evidence limitations

The local Task 1 demo path is explicitly labelled as not Claude-generated.
No live Claude quality, latency, or cost results are claimed because valid
API access was not available during this implementation. Replace this note
with the exact observed setup and test evidence before submission.
