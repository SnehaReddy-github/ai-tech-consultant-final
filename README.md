# AI Tech Consultant

A three-part prototype for support knowledge retrieval, email assistance,
and meeting-to-scope drafting.

## Components

- **Task 1 — Knowledge Brain:** Python/FastAPI, sitemap synchronization,
  article retrieval, source links, image/OCR support, and human review.
- **Task 2 — Inbox Agent:** TypeScript/Express email classification,
  drafting, feedback learning, and tests for safe workflows.
- **Task 3 — Meeting to Scope:** Python/FastAPI transcript-to-scope draft,
  clarifying questions, preliminary task estimates, Task 1 API consultation,
  and follow-up change comparison.

## Requirements

- Python virtual environment with the project dependencies installed.
- Node.js and npm.
- Task 1 runs locally on port 8002 by default.
- Task 2 dependencies installed with `npm install`.

## Run Task 1

From the repository root, activate `.venv`, then run:

```powershell
python -m uvicorn main:app --app-dir task1-knowledge-brain/app --host 127.0.0.1 --port 8002
```

API docs: http://127.0.0.1:8002/docs

## Run Task 2

```powershell
cd task2-inbox-agent
npm install
npm test
npm run typecheck
npm start
```

## Run Task 3

In another terminal, from the repository root:

```powershell
$env:KNOWLEDGE_API_URL = "http://127.0.0.1:8002"
python -m uvicorn main:app --app-dir task3-meeting-to-scope/app --host 127.0.0.1 --port 8003
```

API docs: http://127.0.0.1:8003/docs

Example request:

```powershell
$body = @{
  transcript = "We need to create a customer dashboard. The admin should review reports."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8003/scope" -Method Post -ContentType "application/json" -Body $body
```

## Tests

```powershell
python -m pytest task1-knowledge-brain/tests -q
python -m pytest task3-meeting-to-scope/tests -q
```

## Important limitations

Task 3 uses simple keyword-based extraction and placeholder estimates. It is
a prototype, not a validated estimation engine. Outputs are drafts and require
human approval. If Task 1 is unavailable, custom-development recommendations
are explicitly blocked for human review.

Task 1 currently supports a transparent local demo path when Claude API access
is unavailable. Do not describe that path as Claude-generated output. Live
Claude integration, end-to-end evaluation, 20+ Task 3 evaluation cases,
recorded role-play meetings, and the demo video must be verified or completed
before claiming full assignment compliance.
