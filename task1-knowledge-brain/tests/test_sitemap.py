
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import database


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    """Give each test its own temporary database."""
    test_db = tmp_path / "test_knowledge.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.initialize_database()
    return test_db


def test_sitemap_adds_new_urls(isolated_database):
    urls = [
        "https://support.example.com/article-one",
        "https://support.example.com/article-two",
    ]

    result = database.sync_sitemap_urls(urls)

    assert result["sitemap_urls"] == 2
    assert result["added"] == 2

    summary = database.get_sitemap_summary()
    assert summary["total_tracked"] == 2
    assert summary["currently_present"] == 2
    assert summary["currently_absent"] == 0


def test_sitemap_does_not_duplicate_existing_urls(isolated_database):
    url = "https://support.example.com/article-one"

    database.sync_sitemap_urls([url])
    result = database.sync_sitemap_urls([url])

    assert result["added"] == 0
    assert result["reappeared"] == 0

    summary = database.get_sitemap_summary()
    assert summary["total_tracked"] == 1
    assert summary["currently_present"] == 1


def test_sitemap_detects_removed_urls(isolated_database):
    first_sitemap = [
        "https://support.example.com/article-one",
        "https://support.example.com/article-two",
    ]
    database.sync_sitemap_urls(first_sitemap)

    result = database.sync_sitemap_urls([
        "https://support.example.com/article-one"
    ])

    assert result["removed_from_sitemap"] == 1

    summary = database.get_sitemap_summary()
    assert summary["total_tracked"] == 2
    assert summary["currently_present"] == 1
    assert summary["currently_absent"] == 1


def test_sitemap_detects_reappearing_urls(isolated_database):
    url = "https://support.example.com/article-one"

    database.sync_sitemap_urls([url])
    database.sync_sitemap_urls([
        "https://support.example.com/article-two"
    ])

    result = database.sync_sitemap_urls([url])

    assert result["reappeared"] == 1

    summary = database.get_sitemap_summary()
    assert summary["currently_present"] == 1
    assert summary["currently_absent"] == 1


def test_sitemap_rejects_empty_sitemap(isolated_database):
    database.sync_sitemap_urls([
        "https://support.example.com/article-one"
    ])

    with pytest.raises(ValueError, match="empty sitemap"):
        database.sync_sitemap_urls([])

    # A failed/empty sync must not mark existing URLs as removed.
    summary = database.get_sitemap_summary()
    assert summary["total_tracked"] == 1
    assert summary["currently_present"] == 1
    assert summary["currently_absent"] == 0
