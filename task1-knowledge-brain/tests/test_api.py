
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import main


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def test_home_returns_service_information(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["version"] == main.app.version


def test_health_returns_healthy_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "task1-knowledge-brain"


def test_stats_returns_knowledge_statistics(client):
    response = client.get("/stats")

    assert response.status_code == 200
    body = response.json()
    assert "article_count" in body
    assert "crawl_queue" in body
    assert "sitemap" in body


def test_search_rejects_empty_query(client):
    response = client.post(
        "/search",
        json={"query": "", "limit": 5},
    )

    assert response.status_code == 422


def test_search_rejects_limit_above_maximum(client):
    response = client.post(
        "/search",
        json={"query": "homepage", "limit": 21},
    )

    assert response.status_code == 422


def test_search_returns_expected_response_fields(client, monkeypatch):
    def fake_search(query, limit=5):
        return [
            {
                "url": "https://example.com/article",
                "title": "Homepage Settings",
                "content": "Configure homepage settings.",
                "updated_at": "2026-10-19T00:00:00+00:00",
                "score": 10,
                "matched_terms": ["homepage"],
                "coverage": 1.0,
                "matched_image_text": True,
            }
        ][:limit]

    monkeypatch.setattr(
        main,
        "search_articles_with_ocr",
        fake_search,
    )

    response = client.post(
        "/search",
        json={"query": "homepage", "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["articles"][0]["title"] == "Homepage Settings"
    assert body["articles"][0]["matched_image_text"] is True


def test_search_returns_empty_results_when_no_matches(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        main,
        "search_articles_with_ocr",
        lambda query, limit=5: [],
    )

    response = client.post(
        "/search",
        json={"query": "nonexistent feature", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["articles"] == []


def test_ask_rejects_empty_question(client):
    response = client.post("/ask", json={"question": ""})

    assert response.status_code == 422


def test_review_tasks_returns_task_list(client):
    response = client.get("/review-tasks?status=all")

    assert response.status_code == 200
    body = response.json()
    assert "tasks" in body
    assert "count" in body
    assert body["count"] == len(body["tasks"])


def test_review_tasks_rejects_invalid_status(client):
    response = client.get("/review-tasks?status=invalid")

    # The review service should reject unsupported status filters.
    assert response.status_code == 422
