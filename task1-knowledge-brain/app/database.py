import hashlib
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "knowledge.db"


def get_connection() -> sqlite3.Connection:
    """Create a database connection with named-column access."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    """Create database tables and safely migrate older databases."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_progress (
                url TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS article_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_url TEXT NOT NULL,
                image_url TEXT NOT NULL,
                alt_text TEXT NOT NULL DEFAULT '',
                caption TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                visual_description TEXT NOT NULL DEFAULT '',
                UNIQUE(article_url, image_url),
                FOREIGN KEY(article_url) REFERENCES articles(url)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sitemap_urls (
                url TEXT PRIMARY KEY,
                is_present INTEGER NOT NULL DEFAULT 1,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_queued_date TEXT NOT NULL
            )
            """
        )

        columns = connection.execute(
            "PRAGMA table_info(article_images)"
        ).fetchall()
        column_names = {column["name"] for column in columns}

        if "visual_description" not in column_names:
            connection.execute(
                """
                ALTER TABLE article_images
                ADD COLUMN visual_description TEXT NOT NULL DEFAULT ''
                """
            )


# ---------------------------------------------------------------------
# Article storage
# ---------------------------------------------------------------------

def save_article(url: str, title: str, content: str) -> str:
    """Save an article and return added, updated, or unchanged."""
    content_hash = hashlib.sha256(
        f"{title}\n{content}".encode("utf-8")
    ).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT content_hash FROM articles WHERE url = ?",
            (url,),
        ).fetchone()

        if existing and existing["content_hash"] == content_hash:
            return "unchanged"

        connection.execute(
            """
            INSERT INTO articles (
                url, title, content, content_hash, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                content_hash = excluded.content_hash,
                updated_at = excluded.updated_at
            """,
            (url, title, content, content_hash, now),
        )

        return "updated" if existing else "added"


# ---------------------------------------------------------------------
# Article image storage
# ---------------------------------------------------------------------

def save_article_images(article_url: str, images: list) -> int:
    """Save image metadata while preserving visual descriptions."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        article = connection.execute(
            "SELECT url FROM articles WHERE url = ?",
            (article_url,),
        ).fetchone()

        if not article:
            raise ValueError(
                f"Save the article before its images: {article_url}"
            )

        new_urls = list(dict.fromkeys(image.url for image in images))

        if new_urls:
            placeholders = ",".join("?" for _ in new_urls)
            connection.execute(
                f"""
                DELETE FROM article_images
                WHERE article_url = ?
                  AND image_url NOT IN ({placeholders})
                """,
                (article_url, *new_urls),
            )
        else:
            connection.execute(
                "DELETE FROM article_images WHERE article_url = ?",
                (article_url,),
            )

        for image in images:
            connection.execute(
                """
                INSERT INTO article_images (
                    article_url, image_url, alt_text,
                    caption, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(article_url, image_url) DO UPDATE SET
                    alt_text = excluded.alt_text,
                    caption = excluded.caption,
                    updated_at = excluded.updated_at
                """,
                (
                    article_url,
                    image.url,
                    image.alt_text,
                    image.caption,
                    now,
                ),
            )

    return len(new_urls)


def get_article_images(article_url: str) -> list[dict]:
    """Return image metadata and visual descriptions."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT image_url, alt_text, caption, visual_description
            FROM article_images
            WHERE article_url = ?
            ORDER BY id
            """,
            (article_url,),
        ).fetchall()

    return [dict(row) for row in rows]


def save_image_description(
    article_url: str,
    image_url: str,
    description: str,
) -> None:
    """Save a visual description for an article image."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE article_images
            SET visual_description = ?, updated_at = ?
            WHERE article_url = ? AND image_url = ?
            """,
            (description, now, article_url, image_url),
        )

        if cursor.rowcount == 0:
            raise ValueError(
                "Image record not found for the supplied article and URL."
            )


# ---------------------------------------------------------------------
# Article search
# ---------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Normalize text for phrase comparisons."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _query_keywords(query: str) -> list[str]:
    """Extract distinct search keywords, excluding common words."""
    terms = list(dict.fromkeys(re.findall(r"[a-z0-9]+", query.lower())))

    stop_words = {
        "a", "an", "and", "are", "can", "could", "did", "do", "does",
        "for", "from", "how", "i", "in", "is", "it", "me", "my", "of",
        "on", "or", "please", "the", "to", "was", "what", "when",
        "where", "which", "who", "why", "with", "would", "you", "your",
    }

    keywords = [term for term in terms if term not in stop_words]
    return keywords or terms


def search_articles(query: str, limit: int = 5) -> list[dict]:
    """
    Search articles using keyword coverage and relevance ranking.

    Uses a more flexible coverage threshold to allow useful candidates
    through to the higher-level image-aware relevance filter.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")

    normalized_query = _normalize_text(query)
    keywords = _query_keywords(query)

    if not normalized_query or not keywords:
        return []

    conditions = []
    parameters = []

    for term in keywords:
        conditions.append(
            "(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)"
        )
        pattern = f"%{term}%"
        parameters.extend([pattern, pattern])

    sql = f"""
        SELECT url, title, content, updated_at
        FROM articles
        WHERE {" OR ".join(conditions)}
    """

    with get_connection() as connection:
        rows = connection.execute(sql, parameters).fetchall()

    scored = []

    for row in rows:
        title = row["title"] or ""
        content = row["content"] or ""
        url = row["url"] or ""

        normalized_title = _normalize_text(title)
        normalized_content = _normalize_text(content)
        normalized_url = url.lower()

        title_words = set(normalized_title.split())
        content_words = set(normalized_content.split())

        title_matches = [
            term for term in keywords if term in title_words
        ]
        content_matches = [
            term for term in keywords if term in content_words
        ]
        matched_terms = set(title_matches) | set(content_matches)

        if not matched_terms:
            continue

        coverage = len(matched_terms) / len(keywords)
        strong_coverage = coverage >= 0.4
        strong_title_match = (
            len(title_matches) >= 2 and coverage >= 0.5
        )

        if not (strong_coverage or strong_title_match):
            continue

        score = len(title_matches) * 8 + len(content_matches) * 2
        score += round(coverage * 10)

        if normalized_query == normalized_title:
            score += 30
        elif (
            len(normalized_query) >= 8
            and normalized_query in normalized_title
        ):
            score += 18

        for index in range(len(keywords) - 1):
            phrase = " ".join(keywords[index:index + 2])
            if phrase in normalized_title:
                score += 5

        if "/support/solutions/articles/" in normalized_url:
            score += 8
        elif re.search(r"/support/solutions/\d+/?$", normalized_url):
            score -= 8
        elif "/support/solutions/folders/" in normalized_url:
            score -= 10

        if len(normalized_content.split()) > 1500 and not title_matches:
            score -= 3

        if score <= 0:
            continue

        scored.append(
            {
                "url": url,
                "title": title,
                "content": content,
                "updated_at": row["updated_at"],
                "score": score,
                "matched_terms": sorted(matched_terms),
                "coverage": round(coverage, 2),
            }
        )

    scored.sort(
        key=lambda item: (
            -item["score"],
            -item["coverage"],
            item["title"].lower(),
        )
    )

    return scored[:limit]
# ---------------------------------------------------------------------
# Crawl queue
# ---------------------------------------------------------------------

def mark_url_pending(url: str) -> None:
    """Register a URL without resetting existing progress."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO crawl_progress (url, status, updated_at)
            VALUES (?, 'pending', ?)
            ON CONFLICT(url) DO NOTHING
            """,
            (url, now),
        )


def get_pending_urls(limit: int = 3) -> list[str]:
    """Return pending URLs in a stable order."""
    if limit < 1:
        raise ValueError("limit must be at least 1")

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT url
            FROM crawl_progress
            WHERE status = 'pending'
            ORDER BY url
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [row["url"] for row in rows]


def mark_url_completed(url: str) -> None:
    """Mark a URL as successfully processed."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE crawl_progress
            SET status = 'completed',
                attempts = attempts + 1,
                last_error = NULL,
                updated_at = ?
            WHERE url = ?
            """,
            (now, url),
        )


def mark_url_failed(url: str, error: str) -> None:
    """Record a failed attempt so it can be retried."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE crawl_progress
            SET status = 'pending',
                attempts = attempts + 1,
                last_error = ?,
                updated_at = ?
            WHERE url = ?
            """,
            (error[:1000], now, url),
        )


def count_articles() -> int:
    """Return the number of stored articles."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM articles"
        ).fetchone()

    return row["total"]


def count_crawl_urls() -> dict[str, int]:
    """Return the number of URLs in each crawl status."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM crawl_progress
            GROUP BY status
            """
        ).fetchall()

    return {row["status"]: row["total"] for row in rows}


# ---------------------------------------------------------------------
# Sitemap synchronization
# ---------------------------------------------------------------------

def sync_sitemap_urls(urls: list[str]) -> dict[str, int]:
    """
    Synchronize a successfully fetched sitemap with the local database.

    New URLs are queued for crawling.
    Missing URLs are marked absent, but their article content is retained.
    Existing articles are queued for recrawling at most once per UTC day.
    """
    cleaned_urls = sorted(
        {
            url.strip()
            for url in urls
            if isinstance(url, str)
            and url.strip().startswith(("https://", "http://"))
        }
    )

    if not cleaned_urls:
        raise ValueError("Refusing to synchronize an empty sitemap.")

    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()

    added = 0
    reappeared = 0
    recrawl_queued = 0
    removed = 0

    with get_connection() as connection:
        previous_rows = connection.execute(
            """
            SELECT url, is_present, last_queued_date
            FROM sitemap_urls
            """
        ).fetchall()

        previous = {
            row["url"]: dict(row)
            for row in previous_rows
        }
        current_urls = set(cleaned_urls)

        # Mark URLs missing from the successfully fetched sitemap as absent.
        for old_url, old_record in previous.items():
            if old_url not in current_urls and old_record["is_present"]:
                connection.execute(
                    """
                    UPDATE sitemap_urls
                    SET is_present = 0
                    WHERE url = ?
                    """,
                    (old_url,),
                )

                connection.execute(
                    """
                    UPDATE crawl_progress
                    SET status = 'removed',
                        updated_at = ?
                    WHERE url = ? AND status = 'pending'
                    """,
                    (now, old_url),
                )
                removed += 1

        for url in cleaned_urls:
            old_record = previous.get(url)

            if old_record is None:
                connection.execute(
                    """
                    INSERT INTO sitemap_urls (
                        url, is_present, first_seen_at,
                        last_seen_at, last_queued_date
                    )
                    VALUES (?, 1, ?, ?, ?)
                    """,
                    (url, now, now, today),
                )

                connection.execute(
                    """
                    INSERT INTO crawl_progress (
                        url, status, attempts, updated_at
                    )
                    VALUES (?, 'pending', 0, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        status = 'pending',
                        last_error = NULL,
                        updated_at = excluded.updated_at
                    """,
                    (url, now),
                )

                added += 1
                continue

            was_present = bool(old_record["is_present"])

            connection.execute(
                """
                UPDATE sitemap_urls
                SET is_present = 1,
                    last_seen_at = ?
                WHERE url = ?
                """,
                (now, url),
            )

            if not was_present:
                connection.execute(
                    """
                    UPDATE sitemap_urls
                    SET last_queued_date = ?
                    WHERE url = ?
                    """,
                    (today, url),
                )

                connection.execute(
                    """
                    INSERT INTO crawl_progress (
                        url, status, attempts, updated_at
                    )
                    VALUES (?, 'pending', 0, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        status = 'pending',
                        last_error = NULL,
                        updated_at = excluded.updated_at
                    """,
                    (url, now),
                )

                reappeared += 1
                continue

            # Recrawl existing articles no more than once each UTC day.
            if old_record["last_queued_date"] != today:
                article_exists = connection.execute(
                    "SELECT 1 FROM articles WHERE url = ?",
                    (url,),
                ).fetchone()

                if article_exists:
                    connection.execute(
                        """
                        INSERT INTO crawl_progress (
                            url, status, attempts, updated_at
                        )
                        VALUES (?, 'pending', 0, ?)
                        ON CONFLICT(url) DO UPDATE SET
                            status = 'pending',
                            last_error = NULL,
                            updated_at = excluded.updated_at
                        """,
                        (url, now),
                    )
                    recrawl_queued += 1

                connection.execute(
                    """
                    UPDATE sitemap_urls
                    SET last_queued_date = ?
                    WHERE url = ?
                    """,
                    (today, url),
                )

    summary = {
        "sitemap_urls": len(cleaned_urls),
        "added": added,
        "reappeared": reappeared,
        "recrawl_queued": recrawl_queued,
        "removed_from_sitemap": removed,
    }

    print("Sitemap sync summary:", summary)
    return summary


def get_sitemap_summary() -> dict[str, int]:
    """Return counts of tracked, present, and absent sitemap URLs."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_tracked,
                SUM(CASE WHEN is_present = 1 THEN 1 ELSE 0 END)
                    AS currently_present,
                SUM(CASE WHEN is_present = 0 THEN 1 ELSE 0 END)
                    AS currently_absent
            FROM sitemap_urls
            """
        ).fetchone()

    return {
        "total_tracked": row["total_tracked"] or 0,
        "currently_present": row["currently_present"] or 0,
        "currently_absent": row["currently_absent"] or 0,
    }


# ---------------------------------------------------------------------
# Direct execution / diagnostics
# ---------------------------------------------------------------------

if __name__ == "__main__":
    initialize_database()

    print(f"Database initialized: {DB_PATH}")
    print(f"Stored articles: {count_articles()}")
    print(f"Crawl progress: {count_crawl_urls()}")
    print(f"Sitemap summary: {get_sitemap_summary()}")

    with get_connection() as connection:
        columns = connection.execute(
            "PRAGMA table_info(article_images)"
        ).fetchall()

    print(
        "Image table columns:",
        [column["name"] for column in columns],
    )

    results = search_articles(
        "How can I customize my website homepage layout?",
        limit=5,
    )

    print("\nSearch results:")
    for result in results:
        print("Score:", result["score"])
        print("Coverage:", result["coverage"])
        print("Title:", result["title"])
        print("URL:", result["url"])
        print("-" * 60)