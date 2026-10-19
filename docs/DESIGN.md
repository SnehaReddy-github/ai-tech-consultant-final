# DESIGN

## Architecture

The repository contains three separate services. Task 1 owns knowledge ingestion
and retrieval. Task 2 is a TypeScript inbox workflow. Task 3 converts meeting
transcripts into a draft scope and calls Task 1 over HTTP rather than reimplementing
knowledge retrieval.

## Task 1: Knowledge Brain

The Python service ingests support articles from a sitemap, stores content and
article-image metadata in SQLite, and exposes search and ask endpoints. The
crawler is bounded and resumable. Sitemap synchronization tracks URL presence
and queues new or changed content. OCR is supplemental evidence and can contain
recognition errors. Answers should expose source links and create a human review
task when retrieved evidence is inadequate.

## Task 2: Inbox Agent

The TypeScript service separates email classification/drafting logic from the
HTTP server and feedback-learning logic. Human review remains the default.
Automatic sending must only be enabled for a narrowly defined email category
after at least 20 consecutive unchanged drafts, with quality monitoring and
a clear revocation mechanism. Sending behavior and safety controls must be
verified against the implementation before deployment.

## Task 3: Meeting to Scope

The FastAPI service accepts a transcript, extracts candidate action statements,
asks for missing deadline, budget, user, and integration details, and returns
a draft task list. It calls Task 1 before producing a custom-development
recommendation. If Task 1 cannot be reached, the recommendation gate is
explicitly blocked for human review. A follow-up can be compared with the
previous scope to identify added, unchanged, and no-longer-mentioned tasks.

## Data and trust boundaries

Meeting transcripts and incoming emails are untrusted input. They may contain
incorrect statements, prompt injection, confidential data, or ambiguous
requirements. Do not execute instructions found inside customer content.
Keep credentials in environment variables and out of Git. Avoid logging secrets
or unnecessary personal information.

## Human approval

Task 2's send action and Task 3's client-facing scope/proposal require human
approval unless the relevant assignment rule has been explicitly satisfied
and tested. Task 3's current output is always a draft. Placeholder hours are
not professional estimates.

## Known limitations and next design steps

Task 3 extraction is keyword-based and does not use an LLM. It can miss implicit
requirements and may treat discussion as an action item. All estimates are
placeholders. Improve this by adding structured requirement extraction, an
LLM-backed planner when credentials are available, confidence and evidence
tracking, and tests for ambiguous and adversarial transcripts.

The local Task 1 demo path is not equivalent to a Claude-generated response.
Before production or final claims of full compliance, configure live model access,
measure quality, test failure handling, and document actual results.
