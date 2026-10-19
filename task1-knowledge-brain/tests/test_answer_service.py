
import sys
from pathlib import Path

import pytest

# Make the Task 1 app modules importable when pytest runs from the project root.
APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import answer_service


@pytest.mark.asyncio
async def test_empty_question_is_rejected():
    with pytest.raises(ValueError, match="Question cannot be empty"):
        await answer_service.answer_question("   ")


@pytest.mark.asyncio
async def test_no_articles_requires_human_review(monkeypatch):
    # This test must not reuse an answer previously approved in the real DB.
    monkeypatch.setattr(
        answer_service,
        "get_approved_answer",
        lambda question: None,
    )
    monkeypatch.setattr(
        answer_service,
        "find_relevant_articles",
        lambda question, limit=5: [],
    )

    result = await answer_service.answer_question("Unknown feature question")

    assert result["status"] == "not_found"
    assert result["sources"] == []
    assert result["needs_human_review"] is True
    assert "review_task_id" in result


@pytest.mark.asyncio
async def test_missing_api_key_uses_free_demo_mode(monkeypatch):
    monkeypatch.setattr(
        answer_service,
        "get_approved_answer",
        lambda question: None,
    )
    monkeypatch.setattr(
        answer_service,
        "find_relevant_articles",
        lambda question, limit=5: [
            {
                "title": "Example support article",
                "url": "https://example.com/article",
                "content": "Example support instructions.",
            }
        ],
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    result = await answer_service.answer_question(
        "How does this example feature work?"
    )

    assert result["status"] == "demo_mode"
    assert result["mode"] == "local_demo"
    assert "not a Claude-generated answer" in result["answer"]
    assert result["sources"][0]["title"] == "Example support article"
    assert result["needs_human_review"] is True


@pytest.mark.asyncio
async def test_answer_uses_claude_and_returns_sources(monkeypatch):
    monkeypatch.setattr(
        answer_service,
        "get_approved_answer",
        lambda question: None,
    )
    monkeypatch.setattr(
        answer_service,
        "find_relevant_articles",
        lambda question, limit=5: [
            {
                "title": "Example support article",
                "url": "https://example.com/article",
                "content": "Example support instructions.",
            }
        ],
    )
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class FakeTextBlock:
        type = "text"
        text = "Follow the instructions in the support article. [1]"

    class FakeResponse:
        content = [FakeTextBlock()]

    class FakeMessages:
        async def create(self, **kwargs):
            assert kwargs["model"] == "test-model"
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    result = await answer_service.answer_question(
        "How does this example feature work?",
        client=FakeClient(),
    )

    assert result["status"] == "answered"
    assert result["mode"] == "claude"
    assert "support article" in result["answer"]
    assert result["sources"][0]["title"] == "Example support article"
    assert result["needs_human_review"] is False
