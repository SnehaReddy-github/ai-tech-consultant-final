# DESIGN — AI Tech Consultant

## 1. Problem and Goals

The AI Tech Consultant combines three workflows into one repository:

1. **Knowledge Brain:** Collect and retrieve support documentation, provide source-linked answers, and flag questions that cannot be answered confidently.
2. **Inbox Agent:** Classify incoming customer emails, generate draft replies, and retain human control over sending.
3. **Meeting to Scope:** Convert meeting transcripts into draft requirements, clarification questions, task lists, and proposed scopes.

The goal is to reduce repetitive work while preserving evidence, traceability, and human approval. The system is a prototype, not a production-ready autonomous service.

## 2. Architecture

The repository separates the three tasks into independent services. Task 1 is the knowledge source; Task 2 handles email workflows; Task 3 creates draft project scopes and consults Task 1 when considering custom development.

### Connection diagram

```text
                 Support Article Sitemap
                          |
                          v
                +-------------------+
                | Task 1: Knowledge |
                | Brain (FastAPI)   |
                | SQLite + Search  |
                +-------------------+
                    ^           ^
                    | HTTP      | HTTP
                    |           |
          +---------+--+     +--+----------------+
          | Task 2:    |     | Task 3:           |
          | Inbox Agent|     | Meeting to Scope  |
          | TypeScript |     | FastAPI           |
          +------------+     +-------------------+
                |                     |
                v                     v
          Human reviews         Human reviews
          and approves drafts   scope/proposal
```

Task 2 and Task 3 should call Task 1 through its documented API rather than duplicating retrieval logic. Human-facing actions remain separate from automated analysis.

## 3. Task 1 — Knowledge Brain

### Responsibilities

Task 1 ingests support articles from a sitemap, stores article content and image metadata in SQLite, and exposes search and question-answering endpoints.

The crawler is designed to be bounded and resumable. Sitemap synchronization tracks URL presence and identifies new or changed content. Article images may provide supplemental evidence; OCR output can contain recognition errors and must not be treated as infallible.

### Design choices

- **Python and FastAPI:** Provide HTTP endpoints and a familiar testing framework.
- **SQLite:** Provides a lightweight local persistence layer without requiring a separate database server.
- **Sitemap-driven discovery:** Establishes a starting point for finding support articles and synchronizing changes.
- **Source links:** Allow users to inspect the documentation behind an answer.
- **Human review:** Unsupported or insufficiently grounded questions should be escalated rather than answered with fabricated information.

### Trust and failure handling

The system should distinguish retrieved evidence from assumptions. If the knowledge base cannot support an answer, it should communicate uncertainty and create or request a human-review task. Network failures, removed URLs, incomplete article extraction, and OCR errors should be included in evaluation scenarios.

The local demo path is not equivalent to a Claude-generated response. Live model performance must not be claimed without successful integration and measured evaluation.

## 4. Task 2 — Inbox Agent

### Responsibilities

Task 2 is a TypeScript service that classifies customer emails and drafts replies. Its architecture separates email-processing logic, the HTTP server, and feedback-learning logic.

The sample dataset contains 50 fictional emails with 50 unique IDs across five categories: support, pricing, sales, meeting, and general.

### Design choices

- **TypeScript:** Adds static type checking to the email-processing workflow.
- **Separate processing and server modules:** Makes classification and drafting logic easier to test independently of HTTP behavior.
- **Feedback learning:** Provides a way to use human edits and decisions to improve later drafts.
- **Human review by default:** Prevents a generated reply from automatically becoming an external commitment.

### Automatic sending safeguards

The assignment specifies that a narrowly defined email category may become eligible for automatic sending only after 20 consecutive unchanged drafts of that kind, with quality monitoring and a revocation mechanism.

This rule must be demonstrated and tested against the actual implementation. A dataset of 50 emails does not establish that the held-out evaluation requirement has been met. Automatic sending should not be enabled for real customer emails based solely on unit-test results.

### Failure handling

Evaluation should cover ambiguous emails, complaints, urgent requests, spam, duplicate messages, incorrect classifications, human overrides, feedback behavior, and quality degradation. The system should fail safely when confidence or policy requirements are not satisfied.

## 5. Task 3 — Meeting to Scope

### Responsibilities

Task 3 accepts a meeting transcript and extracts candidate action statements. It identifies missing information about deadlines, budgets, users, and integrations, then produces a draft task list and scope.

Before recommending custom development, it calls Task 1 to check whether an existing support solution may already address the request.

### Design choices

- **Python and FastAPI:** Provide an HTTP interface for transcript processing and scope generation.
- **Task 1 integration:** Reduces duplicated knowledge and helps identify existing solutions.
- **Clarification questions:** Expose missing requirements rather than silently inventing them.
- **Follow-up comparison:** Identifies added, unchanged, and no-longer-mentioned tasks when a later meeting changes the scope.
- **Human approval:** Keeps client-facing proposals as drafts until reviewed.

### Known limitations

The current extraction is keyword-based rather than LLM-based. It may miss implicit requirements or mistake discussion for a confirmed action. Placeholder hours are not professional estimates.

If Task 1 is unavailable, the custom-development recommendation gate should remain blocked for human review. Future improvements include structured requirement extraction, evidence and confidence tracking, improved estimation, and adversarial transcript testing.

## 6. Model Choices and Alternatives

The implementation should distinguish between deterministic application logic and model-generated outputs.

| Approach | Reason for use | Limitation |
|---|---|---|
| Keyword-based extraction | Simple and testable for the current Task 3 prototype | Misses context and implicit requirements |
| Retrieval from stored articles | Grounds answers in available support content | Depends on content coverage and extraction quality |
| Claude integration | Intended for model-based reasoning and generation where configured | Live performance cannot be claimed without working credentials and evaluation |
| Human review | Controls uncertain answers and external actions | Requires reviewer time |

Claude API access was unavailable in the reported setup. Therefore, live Claude accuracy, latency, cost, and comparative model performance have not been measured. Model selection should be revisited after representative evaluation cases and live API access are available.

## 7. Data Security and Trust Boundaries

Incoming emails and meeting transcripts are untrusted input. They may contain inaccurate information, confidential data, ambiguous instructions, or prompt-injection attempts.

The application should:

- Treat customer-provided instructions as data, not as authority to override system policies.
- Keep API keys and credentials in environment variables.
- Exclude secrets, virtual environments, local databases, and generated dependency directories from Git.
- Avoid logging unnecessary personal or confidential information.
- Require human approval for client-facing actions unless an explicitly permitted and tested policy applies.

## 8. Testing and Evaluation Strategy

Automated tests verify selected behaviors but do not establish production readiness.

The latest reported local results are:

- Task 1: 43 tests passed.
- Task 2: 25 tests passed; TypeScript type-check passed.
- Task 3: 5 tests passed.

These results total 73 reported passing tests. Systematic answer quality, held-out email performance, scope quality, live model costs, and end-to-end integration remain separate evaluation requirements.

The evaluation plan is documented in `EVALS.md`. It should include at least 20 evaluation cases for each task, realistic failure cases, model comparisons where possible, and measured results. Unmeasured metrics must remain explicitly marked as pending.

## 9. Next Steps

1. Build the required evaluation cases for all three tasks.
2. Verify a held-out email dataset and the automatic-send safeguards.
3. Record at least three client meeting role-plays, including a follow-up.
4. Verify Task 1 integration from Tasks 2 and 3.
5. Configure and evaluate live Claude access if credentials become available.
6. Complete the demo video and inspect the final repository for secrets and generated files.
7. Update documentation with reproducible results rather than estimates or unsupported claims.
