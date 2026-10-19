
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "task1-knowledge-brain" / "app"
sys.path.insert(0, str(APP_DIR))

import database


@pytest.fixture
def temporary_database(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_knowledge.db"
    monkeypatch.setattr(database, "DB_PATH", test_db_path)
    database.initialize_database()
    return test_db_path


def test_save_new_article(temporary_database):
    result = database.save_article(
        "https://example.com/article/1",
        "Test Article",
        "This is test content.",
    )
    assert result == "added"
    assert database.count_articles() == 1


def test_unchanged_article_is_not_rewritten(temporary_database):
    url = "https://example.com/article/1"
    first = database.save_article(url, "Test Article", "Same content")
    second = database.save_article(url, "Test Article", "Same content")

    assert first == "added"
    assert second == "unchanged"
    assert database.count_articles() == 1


def test_changed_article_is_updated(temporary_database):
    url = "https://example.com/article/1"
    database.save_article(url, "Test Article", "Old content")

    result = database.save_article(url, "Test Article", "Updated content")

    assert result == "updated"
    assert database.count_articles() == 1


def test_save_and_retrieve_image(temporary_database):
    article_url = "https://example.com/article/1"
    image_url = "https://example.com/image.png"
    database.save_article(article_url, "Test Article", "Content")

    class Image:
        url = image_url
        alt_text = "Example image"
        caption = "Example caption"

    assert database.save_article_images(article_url, [Image()]) == 1
    images = database.get_article_images(article_url)

    assert len(images) == 1
    assert images[0]["image_url"] == image_url
    assert images[0]["alt_text"] == "Example image"
    assert images[0]["visual_description"] == ""


def test_visual_description_survives_image_update(temporary_database):
    article_url = "https://example.com/article/1"
    image_url = "https://example.com/image.png"
    database.save_article(article_url, "Test Article", "Content")

    class Image:
        url = image_url
        alt_text = "Original alt text"
        caption = "Original caption"

    database.save_article_images(article_url, [Image()])
    database.save_image_description(
        article_url, image_url, "A screenshot showing dashboard settings."
    )

    Image.alt_text = "Updated alt text"
    Image.caption = "Updated caption"
    database.save_article_images(article_url, [Image()])

    images = database.get_article_images(article_url)
    assert images[0]["alt_text"] == "Updated alt text"
    assert images[0]["caption"] == "Updated caption"
    assert images[0]["visual_description"] == (
        "A screenshot showing dashboard settings."
    )


def test_crawl_progress(temporary_database):
    url = "https://example.com/article/1"
    database.mark_url_pending(url)

    assert database.get_pending_urls() == [url]

    database.mark_url_completed(url)

    assert database.get_pending_urls() == []
    assert database.count_crawl_urls() == {"completed": 1}


def test_failed_url_can_be_retried(temporary_database):
    url = "https://example.com/article/1"
    database.mark_url_pending(url)
    database.mark_url_failed(url, "Temporary network error")

    assert database.get_pending_urls() == [url]
    assert database.count_crawl_urls() == {"pending": 1}


def test_invalid_pending_limit(temporary_database):
    with pytest.raises(ValueError):
        database.get_pending_urls(limit=0)


def test_search_finds_article_by_content(temporary_database):
    database.save_article(
        "https://example.com/dashboard",
        "Dashboard Guide",
        "Configure dashboard settings and profile options.",
    )

    results = database.search_articles("dashboard settings")

    assert len(results) == 1
    assert results[0]["title"] == "Dashboard Guide"
    assert results[0]["score"] > 0


def test_search_ranks_title_matches_higher(temporary_database):
    database.save_article(
        "https://example.com/a",
        "Dashboard Settings Guide",
        "General product instructions.",
    )
    database.save_article(
        "https://example.com/b",
        "General Guide",
        "Learn about dashboard settings here.",
    )

    results = database.search_articles("dashboard settings")

    assert len(results) == 2
    assert results[0]["title"] == "Dashboard Settings Guide"


def test_search_returns_empty_for_no_matches(temporary_database):
    database.save_article(
        "https://example.com/a",
        "Dashboard Guide",
        "Configure your dashboard.",
    )

    assert database.search_articles("unrelatedxyz") == []


def test_search_rejects_invalid_limit(temporary_database):
    with pytest.raises(ValueError):
        database.search_articles("dashboard", limit=0)


def test_search_handles_empty_query(temporary_database):
    database.save_article(
        "https://example.com/a",
        "Dashboard Guide",
        "Configure your dashboard.",
    )

    assert database.search_articles("") == []
