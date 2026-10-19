from typing import Optional
import os
import re

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="Meeting to Scope",
    description="Creates a draft project scope from meeting transcripts.",
    version="1.0.0",
)

KNOWLEDGE_API = os.getenv(
    "KNOWLEDGE_API_URL", "http://127.0.0.1:8002"
)


class ScopeRequest(BaseModel):
    transcript: str = Field(min_length=20)
    follow_up: Optional[str] = None
    original_scope: Optional[dict] = None


def extract_tasks(transcript: str) -> list[dict]:
    """Extract action-like sentences as draft tasks."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", transcript)
    tasks = []
    keywords = (
        "build", "create", "develop", "implement", "integrate",
        "design", "add", "automate", "update", "need", "require",
        "should", "must", "dashboard", "report", "website", "api",
    )

    for sentence in sentences:
        sentence = sentence.strip(" \t-*")
        if len(sentence) < 12:
            continue
        if any(word in sentence.lower() for word in keywords):
            tasks.append({
                "task": sentence,
                "estimated_hours": 4,
                "estimate_is_placeholder": True,
            })

    # Avoid returning duplicate task sentences.
    unique = []
    seen = set()
    for task in tasks:
        key = task["task"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(task)

    return unique[:20]


def ask_knowledge_brain(question: str) -> dict:
    """Call Task 1 instead of duplicating its knowledge retrieval."""
    try:
        response = httpx.post(
            f"{KNOWLEDGE_API}/ask",
            json={"question": question},
            timeout=8.0,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "available": True,
            "result": data,
            "message": "Task 1 was consulted; verify its sources.",
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "available": False,
            "result": None,
            "message": (
                "Knowledge Brain was unavailable. "
                "Custom-development recommendations require human review."
            ),
            "error": str(exc),
        }


def build_scope(transcript: str, follow_up: Optional[str] = None,
                original_scope: Optional[dict] = None) -> dict:
    combined = transcript
    if follow_up:
        combined += "\nFollow-up:\n" + follow_up

    tasks = extract_tasks(combined)
    questions = []

    if not tasks:
        questions.append(
            "What specific deliverables should the team build?"
        )
    if not re.search(r"\b(deadline|by \w+|within \d+ days?)\b",
                     combined, re.I):
        questions.append("What is the target deadline?")
    if not re.search(r"\b(budget|₹|\$|cost|estimate)\b", combined, re.I):
        questions.append("Is there a target budget or spending limit?")
    if not re.search(r"\b(user|customer|admin|staff|employee)\b",
                     combined, re.I):
        questions.append("Who are the intended users?")
    if not re.search(r"\b(integrat|api|connect|third.party)\b",
                     combined, re.I):
        questions.append(
            "Are integrations with existing systems required?"
        )

    knowledge = ask_knowledge_brain(
        "Check existing documentation before recommending custom development. "
        "Meeting requirements: " + combined[:2500]
    )

    previous_tasks = []
    if original_scope:
        previous_tasks = original_scope.get("tasks", [])

    old_text = {
        str(item.get("task", "")).strip().lower()
        for item in previous_tasks
    }
    new_text = {
        str(item.get("task", "")).strip().lower()
        for item in tasks
    }

    changes = {
        "added": sorted(new_text - old_text) if follow_up else [],
        "unchanged": sorted(new_text & old_text) if follow_up else [],
        "removed_or_not_mentioned": (
            sorted(old_text - new_text) if follow_up else []
        ),
    }

    total_hours = sum(t["estimated_hours"] for t in tasks)

    return {
        "status": "draft_requires_human_approval",
        "scope_summary": (
            "Draft scope derived from the meeting transcript. "
            "Confirm requirements before sharing with a client."
        ),
        "requirements_source": "meeting_transcript",
        "tasks": tasks,
        "placeholder_total_hours": total_hours,
        "estimate_warning": (
            "Each task currently uses a placeholder 4-hour estimate. "
            "These are not validated project estimates."
        ),
        "clarifying_questions": questions,
        "knowledge_brain": knowledge,
        "custom_development_gate": (
            "Review Task 1 evidence before proposing custom development."
            if knowledge["available"] else
            "Blocked for recommendation: Task 1 unavailable; "
            "obtain human review before suggesting custom development."
        ),
        "follow_up_changes": changes,
        "client_approval_required": True,
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "meeting-to-scope"}


@app.post("/scope")
def create_scope(request: ScopeRequest):
    return build_scope(
        request.transcript,
        request.follow_up,
        request.original_scope,
    )
