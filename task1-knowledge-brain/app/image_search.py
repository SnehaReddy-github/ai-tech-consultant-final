
import re
from urllib.parse import urlsplit

from database import get_connection, search_articles


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but",
    "by", "can", "could", "did", "do", "does", "for", "from",
    "had", "has", "have", "he", "her", "here", "how", "i", "if",
    "in", "into", "is", "it", "its", "me", "my", "of", "on",
    "or", "our", "please", "should", "so", "that", "the", "their",
    "them", "there", "these", "they", "this", "to", "us", "was",
    "we", "were", "what", "when", "where", "which", "who", "why",
    "will", "with", "would", "you", "your", "not",
}

GENERIC_TERMS = {
    "help", "issue", "issues", "question", "questions",
    "thing", "things", "work", "working", "broken",
    "fix", "fixing", "troubleshoot", "troubleshooting",
    "problem", "problems", "please",
}


def _tokens(text: str) -> list[str]:
    """Convert text into lowercase alphanumeric words."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _keywords(query: str) -> list[str]:
    """Keep unique, useful search terms."""
    words = _tokens(query)
    return list(dict.fromkeys(
        word for word in words
        if word not in STOP_WORDS and word not in GENERIC_TERMS
    ))


def _article_key(url: str) -> str:
    """Identify URLs for the same support article."""
    path = urlsplit(url).path.rstrip("/")
    match = re.search(r"/(120\d{8,})(?:-|$)", path)

    if match:
        return match.group(1)

    return path.lower()


def _score_article(
    title: str,
    content: str,
    image_text: str,
    query: str,
    keywords: list[str],
) -> dict:
    """Score an article using its title, body, and associated image text."""
    title_tokens = set(_tokens(title))
    content_tokens = set(_tokens(content))
    image_tokens = set(_tokens(image_text))

    title_matches = set(keywords) & title_tokens
    content_matches = set(keywords) & content_tokens
    image_matches = set(keywords) & image_tokens

    matched_terms = title_matches | content_matches | image_matches
    coverage = len(matched_terms) / max(len(keywords), 1)

    normalized_title = " ".join(_tokens(title))
    normalized_content = " ".join(_tokens(content))
    normalized_keywords = " ".join(keywords)

    title_phrase_match = (
        len(keywords) >= 2
        and normalized_keywords in normalized_title
    )
    content_phrase_match = (
        len(keywords) >= 2
        and normalized_keywords in normalized_content
    )

    score = (
        len(title_matches) * 8
        + len(content_matches) * 2
        + len(image_matches) * 0.5
        + round(coverage * 5)
    )

    if title_phrase_match:
        score += 12
    elif content_phrase_match:
        score += 5

    # For longer queries, a strong title match can be useful even when
    # some query terms are absent from the currently indexed articles.
    if len(keywords) >= 3:
        if not matched_terms or (
            len(matched_terms) < 2 and not title_matches
        ):
            score = 0
    elif len(keywords) == 2:
        if len(matched_terms) < 2 and not title_phrase_match:
            score = 0
    elif len(keywords) == 1:
        if not title_matches:
            score = 0

    return {
        "score": score,
        "coverage": round(coverage, 3),
        "matched_terms": sorted(matched_terms),
        "matched_image_text": bool(image_matches),
        "title_match_count": len(title_matches),
        "content_match_count": len(content_matches),
        "image_match_count": len(image_matches),
        "phrase_match": title_phrase_match or content_phrase_match,
    }


def _merge_articles(existing: dict, candidate: dict) -> dict:
    """Keep the stronger result and preserve useful metadata."""
    if candidate.get("score", 0) > existing.get("score", 0):
        stronger, weaker = candidate, existing
    else:
        stronger, weaker = existing, candidate

    merged = dict(stronger)

    for field in ("title", "content", "updated_at"):
        if not merged.get(field) and weaker.get(field):
            merged[field] = weaker[field]

    merged["matched_terms"] = sorted(
        set(existing.get("matched_terms", []))
        | set(candidate.get("matched_terms", []))
    )
    merged["matched_image_text"] = (
        existing.get("matched_image_text", False)
        or candidate.get("matched_image_text", False)
    )

    return merged


def search_articles_with_ocr(query: str, limit: int = 5) -> list[dict]:
    """
    Search support articles and OCR text from associated images.

    Searches individual keywords as well as the full cleaned query,
    so missing query terms do not prevent relevant articles from being
    considered. Returns the original support article URLs.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")

    keywords = _keywords(query)

    if not keywords:
        return []

    candidates = {}
    candidate_limit = max(limit * 20, 50)

    # Search the complete query and individual terms. A search backend
    # may return nothing for the complete query if some terms are absent.
    search_queries = [" ".join(keywords)]
    search_queries.extend(keywords)
    search_queries = list(dict.fromkeys(search_queries))

    for search_query in search_queries:
        for article in search_articles(
            search_query,
            limit=candidate_limit,
        ):
            key = _article_key(article["url"])

            result = _score_article(
                title=article.get("title", ""),
                content=article.get("content", ""),
                image_text="",
                query=query,
                keywords=keywords,
            )

            candidate = {**article, **result}

            if candidate["score"] <= 0:
                continue

            if key in candidates:
                candidates[key] = _merge_articles(
                    candidates[key], candidate
                )
            else:
                candidates[key] = candidate

    # Include articles that match text extracted from their images.
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                a.url,
                a.title,
                a.content,
                a.updated_at,
                i.alt_text,
                i.caption,
                i.visual_description
            FROM articles AS a
            JOIN article_images AS i ON i.article_url = a.url
            WHERE TRIM(COALESCE(i.visual_description, '')) <> ''
            """
        ).fetchall()

    image_text_by_key = {}

    for row in rows:
        key = _article_key(row["url"])

        image_text = " ".join(
            part or ""
            for part in (
                row["alt_text"],
                row["caption"],
                row["visual_description"],
            )
        )

        if key not in image_text_by_key:
            image_text_by_key[key] = {
                "url": row["url"],
                "title": row["title"] or "",
                "content": row["content"] or "",
                "updated_at": row["updated_at"],
                "image_text": image_text,
            }
        else:
            image_text_by_key[key]["image_text"] += " " + image_text

    for key, article in image_text_by_key.items():
        result = _score_article(
            title=article["title"],
            content=article["content"],
            image_text=article["image_text"],
            query=query,
            keywords=keywords,
        )

        if result["score"] <= 0:
            continue

        candidate = {
            "url": article["url"],
            "title": article["title"],
            "content": article["content"],
            "updated_at": article["updated_at"],
            **result,
        }

        if key in candidates:
            candidates[key] = _merge_articles(
                candidates[key], candidate
            )
        else:
            candidates[key] = candidate

    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            -item.get("score", 0),
            -item.get("coverage", 0),
            item.get("title", "").lower(),
        ),
    )

    return ranked[:limit]
