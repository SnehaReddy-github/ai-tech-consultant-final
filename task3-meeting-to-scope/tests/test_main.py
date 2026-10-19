from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def fake_knowledge(question):
    return {
        "available": True,
        "result": {"status": "demo_mode", "answer": "Demo evidence"},
        "message": "Mocked for testing",
    }


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_scope_returns_tasks_and_requires_approval(monkeypatch):
    monkeypatch.setattr(main, "ask_knowledge_brain", fake_knowledge)
    response = client.post("/scope", json={
        "transcript": (
            "We need to create a customer dashboard. "
            "The admin should review reports."
        )
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) >= 1
    assert data["client_approval_required"] is True
    assert data["status"] == "draft_requires_human_approval"


def test_scope_flags_missing_details(monkeypatch):
    monkeypatch.setattr(main, "ask_knowledge_brain", fake_knowledge)
    response = client.post("/scope", json={
        "transcript": "We need to create a customer dashboard."
    })
    data = response.json()
    assert data["clarifying_questions"]
    assert data["estimate_warning"]


def test_knowledge_brain_unavailable_blocks_recommendation(monkeypatch):
    monkeypatch.setattr(main, "ask_knowledge_brain", lambda q: {
        "available": False,
        "result": None,
        "message": "unavailable",
        "error": "connection refused",
    })
    response = client.post("/scope", json={
        "transcript": "We need to develop a website for customers."
    })
    data = response.json()
    assert "Blocked" in data["custom_development_gate"]
    assert data["client_approval_required"] is True


def test_follow_up_compares_scope(monkeypatch):
    monkeypatch.setattr(main, "ask_knowledge_brain", fake_knowledge)
    response = client.post("/scope", json={
        "transcript": "We need to create a customer dashboard.",
        "follow_up": "We also need to implement an API integration.",
        "original_scope": {
            "tasks": [{"task": "We need to create a customer dashboard."}]
        },
    })
    data = response.json()
    assert data["follow_up_changes"]["added"]
    assert data["follow_up_changes"]["unchanged"]
