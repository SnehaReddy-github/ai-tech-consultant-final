
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from answer_service import answer_question
from database import (
    count_articles,
    count_crawl_urls,
    get_sitemap_summary,
    initialize_database,
)
from expert_review import (
    approve_review_task,
    initialize_review_queue,
    list_review_tasks,
    reject_review_task,
)
from image_search import search_articles_with_ocr

app = FastAPI(
    title="AI Tech Consultant - Knowledge Brain",
    description=(
        "Knowledge search, OCR-aware retrieval, grounded answers, "
        "and human expert review API for Task 1."
    ),
    version="0.6.0",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)


class ApproveRequest(BaseModel):
    approved_answer: str = Field(..., min_length=1, max_length=10000)


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=2000)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    initialize_review_queue()


@app.get("/")
def home():
    return {
        "message": "AI Tech Consultant Knowledge Brain API",
        "status": "running",
        "version": app.version,
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "task1-knowledge-brain",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/stats")
def knowledge_stats():
    """Return knowledge-base and crawl progress information."""
    try:
        return {
            "service": "task1-knowledge-brain",
            "article_count": count_articles(),
            "crawl_queue": count_crawl_urls(),
            "sitemap": get_sitemap_summary(),
        }
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve knowledge-base statistics.",
        ) from exc


@app.post("/search")
def search_knowledge(request: SearchRequest):
    """
    Search article content and associated image OCR text.

    Returns source URLs, relevance scores, matched terms, and an
    indicator of whether OCR image text matched the query.
    """
    try:
        articles = search_articles_with_ocr(
            request.query,
            limit=request.limit,
        )
        return {
            "query": request.query,
            "count": len(articles),
            "articles": articles,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except (RuntimeError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Knowledge search failed. Check the knowledge database.",
        ) from exc


@app.post("/ask")
async def ask_question(request: AskRequest):
    """Answer a question using the knowledge base and review workflow."""
    try:
        return await answer_question(request.question)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except anthropic.APIError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "The Claude API request failed. Check API access "
                "and try again."
            ),
        ) from exc


@app.get("/review-tasks")
def get_review_tasks(
    status: str = Query(
        default="pending",
        description="Filter by pending, approved, rejected, or all.",
    ),
):
    """List human expert review tasks."""
    try:
        tasks = list_review_tasks(status)
        return {
            "tasks": tasks,
            "count": len(tasks),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@app.post("/review-tasks/{task_id}/approve")
def approve_task(task_id: int, request: ApproveRequest):
    """Approve an expert answer for future knowledge-base use."""
    try:
        return approve_review_task(
            task_id,
            request.approved_answer,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/review-tasks/{task_id}/reject")
def reject_task(task_id: int, request: RejectRequest):
    """Reject an expert review task."""
    try:
        return reject_review_task(
            task_id,
            request.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
