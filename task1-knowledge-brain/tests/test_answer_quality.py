
import sys
from pathlib import Path

import pytest

# Make Task 1 app modules importable from the project root.
APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import answer_service


def test_valid_citation_is_accepted():
    sources = [{"id": 1, "title": "Support article", "url": "https://example.com/1"}]

    assert answer_service._has_invalid_citations(
        "Follow these documented steps. [1]", sources
    ) is False


def test_unknown_citation_is_rejected():
    sources = [{"id": 1, "title": "Support article", "url": "https://example.com/1"}]

    assert answer_service._has_invalid_citations(
        "Follow these documented steps. [2]", sources
    ) is True


def test_answer_without_citations_is_not_flagged_as_invalid():
    sources = [{"id": 1, "title": "Support article", "url": "https://example.com/1"}]

    assert answer_service._has_invalid_citations(
        "The article describes the feature.", sources
    ) is False


@pytest.mark.parametrize(
    "answer",
    [
        "I cannot determine this from the supplied articles.",
        "The articles do not specify this information.",
        "There is insufficient information to answer.",
    ],
)
def test_uncertain_answers_are_detected(answer):
    assert answer_service._answer_claims_uncertainty(answer) is True


def test_clear_answer_is_not_flagged_as_uncertain():
    assert answer_service._answer_claims_uncertainty(
        "Open the dashboard and select the documented setting. [1]"
    ) is False


def test_duplicate_articles_are_removed():
    articles = [
        {
            "title": "Dashboard Guide",
            "url": "https://example.com/dashboard/",
            "content": "First copy",
        },
        {
            "title": "Dashboard Guide",
            "url": "https://example.com/dashboard",
            "content": "Duplicate copy",
        },
        {
            "title": "Profile Guide",
            "url": "https://example.com/profile",
            "content": "Profile instructions",
        },
    ]

    result = answer_service._deduplicate_articles(articles)

    assert len(result) == 2
    assert result[0]["title"] == "Dashboard Guide"
    assert result[1]["title"] == "Profile Guide"


@pytest.mark.asyncio
async def test_exact_approved_answer_is_reused_without_search(monkeypatch):
    approved_record = {
        "id": 42,
        "question": "How do I change my homepage?",
        "approved_answer": "Use the documented homepage settings.",
    }

    monkeypatch.setattr(
        answer_service,
        "get_approved_answer",
        lambda question: approved_record,
    )

    def unexpected_search(*args, **kwargs):
        pytest.fail("Article search should not run for an approved answer.")

    monkeypatch.setattr(answer_service, "find_relevant_articles", unexpected_search)

    result = await answer_service.answer_question("How do I change my homepage?")

    assert result["status"] == "answered"
    assert result["mode"] == "approved_expert_answer"
    assert result["answer"] == approved_record["approved_answer"]
    assert result["review_task_id"] == 42
    assert result["needs_human_review"] is False


@pytest.mark.asyncio
async def test_uncertain_claude_answer_goes_to_human_review(monkeypatch):
    monkeypatch.setattr(answer_service, "get_approved_answer", lambda question: None)
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
    monkeypatch.setattr(
        answer_service,
        "create_review_task",
        lambda question, reason: {"id": 99},
    )
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class FakeTextBlock:
        type = "text"
        text = "The articles do not specify the answer."

    class FakeResponse:
        content = [FakeTextBlock()]

    class FakeMessages:
        async def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    result = await answer_service.answer_question(
        "How does this feature work?",
        client=FakeClient(),
    )

    assert result["status"] == "low_confidence"
    assert result["needs_human_review"] is True
    assert result["review_task_id"] == 99


@pytest.mark.asyncio
async def test_invalid_claude_citation_goes_to_human_review(monkeypatch):
    monkeypatch.setattr(answer_service, "get_approved_answer", lambda question: None)
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
    monkeypatch.setattr(
        answer_service,
        "create_review_task",
        lambda question, reason: {"id": 100},
    )
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class FakeTextBlock:
        type = "text"
        text = "Follow these instructions. [7]"

    class FakeResponse:
        content = [FakeTextBlock()]

    class FakeMessages:
        async def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    result = await answer_service.answer_question(
        "How does this feature work?",
        client=FakeClient(),
    )

    assert result["status"] == "low_confidence"
    assert result["needs_human_review"] is True
    assert result["review_task_id"] == 100
