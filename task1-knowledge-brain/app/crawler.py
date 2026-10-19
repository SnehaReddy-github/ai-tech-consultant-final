
import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from database import (
    initialize_database,
    save_article,
    save_article_images,
    mark_url_pending,
    get_pending_urls,
    mark_url_completed,
    count_articles,
    count_crawl_urls,
    get_connection,
    get_sitemap_summary,
)
from sitemap import discover_urls


USER_AGENT = "AI-Tech-Consultant-KnowledgeBrain/1.0"
BATCH_SIZE = 10
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 3
MAX_QUEUE_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30.0

SUPPORT_HOST = "support.brilliantdirectories.com"
SUPPORT_PREFIX = "/support/solutions/"

ARTICLE_SELECTORS = [
    '[itemprop="articleBody"]',
    ".article-body",
    ".article__body",
    ".solution-content",
    ".solution-article",
    ".ticket-description",
    "#article-body",
    "#solution-content",
]

NOISE_SELECTORS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "noscript",
    "form",
    "aside",
    "button",
    "input",
    "select",
    "textarea",
    '[role="navigation"]',
    '[aria-label*="breadcrumb" i]',
    ".breadcrumb",
    ".breadcrumbs",
    ".sidebar",
    ".related-articles",
    ".related-questions",
    ".suggested-articles",
    ".article-feedback",
    ".article-vote",
    ".social-share",
    ".pagination",
    ".cookie-banner",
]


@dataclass
class ArticleImage:
    url: str
    alt_text: str
    caption: str = ""


@dataclass
class Article:
    url: str
    title: str
    content: str
    images: list[ArticleImage] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


def ensure_failure_count_column() -> None:
    """Add a separate failure counter without deleting existing data."""
    with get_connection() as connection:
        columns = connection.execute(
            "PRAGMA table_info(crawl_progress)"
        ).fetchall()

        column_names = {column["name"] for column in columns}

        if "failure_count" not in column_names:
            connection.execute(
                """
                ALTER TABLE crawl_progress
                ADD COLUMN failure_count INTEGER NOT NULL DEFAULT 0
                """
            )


def normalize_url(url: str, base_url: str = "") -> str | None:
    """Normalize supported public support-center URLs."""
    absolute_url = urljoin(base_url, url) if base_url else url
    absolute_url, _fragment = urldefrag(absolute_url)
    parsed = urlparse(absolute_url)

    if parsed.scheme not in {"http", "https"}:
        return None

    if parsed.netloc.lower() != SUPPORT_HOST:
        return None

    if not parsed.path.startswith(SUPPORT_PREFIX):
        return None

    path = parsed.path.rstrip("/")

    valid_path = (
        re.fullmatch(r"/support/solutions/\d+", path)
        or re.fullmatch(
            r"/support/solutions/articles/\d+(?:-[^/]*)?",
            path,
        )
        or re.fullmatch(
            r"/support/solutions/folders/\d+(?:-[^/]*)?",
            path,
        )
    )

    if not valid_path:
        return None

    return f"https://{SUPPORT_HOST}{path}"


def is_article_url(url: str) -> bool:
    """Check whether a URL belongs to the supported solution center."""
    return normalize_url(url) is not None


def extract_links(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Extract supported solution-center links before removing navigation."""
    found = set()

    for anchor in soup.select("a[href]"):
        clean_url = normalize_url(anchor.get("href", ""), page_url)

        if clean_url and clean_url != page_url:
            found.add(clean_url)

    return sorted(found)


def extract_images(element: Tag, page_url: str) -> list[ArticleImage]:
    """Extract image URLs, alt text, captions, and nearby article context."""
    images: list[ArticleImage] = []
    seen: set[str] = set()

    for image in element.select("img"):
        candidates = [
            image.get("src"),
            image.get("data-src"),
            image.get("data-original"),
            image.get("data-lazy-src"),
            image.get("data-original-src"),
        ]

        # Include responsive and lazy-loaded image sources.
        for attribute in ("srcset", "data-srcset"):
            srcset = image.get(attribute)

            if srcset:
                candidates.extend(
                    item.strip().split()[0]
                    for item in srcset.split(",")
                    if item.strip()
                )

        image_url = None

        for candidate in candidates:
            if not candidate:
                continue

            candidate = candidate.strip()

            if candidate.startswith("data:"):
                continue

            resolved_url = urljoin(page_url, candidate)
            parsed_url = urlparse(resolved_url)

            if parsed_url.scheme in {"http", "https"}:
                image_url = resolved_url
                break

        if not image_url or image_url in seen:
            continue

        seen.add(image_url)

        figure = image.find_parent("figure")
        caption_element = figure.find("figcaption") if figure else None

        caption = (
            caption_element.get_text(" ", strip=True)
            if caption_element
            else ""
        )

        alt_text = image.get("alt", "").strip()

        if not alt_text:
            alt_text = image.get("title", "").strip()

        # Nearby text provides context, not a verified visual description.
        parent = image.parent
        nearby_text = ""

        for _ in range(3):
            if not isinstance(parent, Tag):
                break

            parent_text = parent.get_text(" ", strip=True)

            if len(parent_text) > len(nearby_text):
                nearby_text = parent_text

            if len(parent_text) >= 20:
                break

            parent = parent.parent

        if not caption and nearby_text:
            caption = nearby_text[:500]

        images.append(
            ArticleImage(
                url=image_url,
                alt_text=alt_text,
                caption=caption[:1000],
            )
        )

    return images


def _clean_page(soup: BeautifulSoup) -> None:
    """Remove navigation and common non-article elements."""
    for selector in NOISE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()

    for element in list(soup.find_all(True)):
        if not element.parent:
            continue

        role = str(element.get("role", "")).casefold()
        aria_label = str(element.get("aria-label", "")).casefold()

        if role in {"navigation", "complementary"}:
            element.decompose()
            continue

        if any(
            word in aria_label
            for word in ("breadcrumb", "related article", "sidebar")
        ):
            element.decompose()


def _choose_content_element(soup: BeautifulSoup) -> Tag:
    """Choose the most likely article body."""
    for selector in ARTICLE_SELECTORS:
        element = soup.select_one(selector)

        if element and element.get_text(" ", strip=True):
            return element

    for selector in ("article", "main", "#content"):
        element = soup.select_one(selector)

        if element and element.get_text(" ", strip=True):
            return element

    body = soup.body or soup
    candidates = body.find_all(["section", "div"], recursive=True)

    if not candidates:
        return body

    useful_candidates = []

    for candidate in candidates:
        text = candidate.get_text(" ", strip=True)

        if len(text) >= 80:
            useful_candidates.append((len(text), candidate))

    if not useful_candidates:
        return body

    useful_candidates.sort(key=lambda item: item[0])
    smallest_length, smallest_candidate = useful_candidates[0]

    if smallest_length < 200 and len(useful_candidates) > 1:
        return useful_candidates[1][1]

    return smallest_candidate


async def fetch_article(
    client: httpx.AsyncClient,
    url: str,
) -> Article:
    """Fetch a page with retries and extract content, images, and links."""
    response = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.get(url)
            response.raise_for_status()
            break

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.HTTPStatusError,
        ) as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code

                # Retry rate limits and server errors, not permanent 4xx.
                if 400 <= status < 500 and status != 429:
                    raise

            if attempt == MAX_RETRIES:
                raise

            await asyncio.sleep(attempt * 2)

    if response is None:
        raise RuntimeError(f"Could not fetch {url}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Find links before removing navigation from the page.
    links = extract_links(soup, url)

    title_element = soup.find("h1") or soup.find("title")

    title = (
        title_element.get_text(" ", strip=True)
        if title_element
        else url.rstrip("/").split("/")[-1]
    )

    _clean_page(soup)
    content_element = _choose_content_element(soup)
    images = extract_images(content_element, url)

    text_blocks = []

    for element in content_element.find_all(
        ["h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote"],
        recursive=True,
    ):
        text = element.get_text(" ", strip=True)

        if text and (not text_blocks or text != text_blocks[-1]):
            text_blocks.append(text)

    content = "\n\n".join(text_blocks)

    if not content:
        content = content_element.get_text(" ", strip=True)

    content = re.sub(r"[ \t]+", " ", content)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    if not content and not images and not links:
        raise ValueError(f"No readable content found at {url}")

    return Article(
        url=url,
        title=title,
        content=content,
        images=images,
        links=links,
    )


def record_failure(url: str, error: str) -> dict:
    """Record a failure and stop automatic retries at the configured limit."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT failure_count
            FROM crawl_progress
            WHERE url = ?
            """,
            (url,),
        ).fetchone()

        current_failures = row["failure_count"] if row else 0
        failures = current_failures + 1

        status = (
            "failed"
            if failures >= MAX_QUEUE_ATTEMPTS
            else "pending"
        )

        connection.execute(
            """
            INSERT INTO crawl_progress (
                url, status, attempts, last_error, updated_at,
                failure_count
            )
            VALUES (?, ?, 1, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                status = excluded.status,
                attempts = crawl_progress.attempts + 1,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at,
                failure_count = excluded.failure_count
            """,
            (url, status, error[:1000], now, failures),
        )

    if status == "failed":
        print(
            f"[GIVE UP] {url} failed {failures} times. "
            "It will not be retried automatically."
        )

    return {
        "url": url,
        "status": status,
        "failure_count": failures,
        "error": error,
    }


async def crawl_one(
    client: httpx.AsyncClient,
    url: str,
) -> dict:
    """Fetch and save one page, then queue its child links."""
    try:
        article = await fetch_article(client, url)

        save_article(
            url=article.url,
            title=article.title,
            content=article.content,
        )

        # Clear stale image records after a successful recrawl.
        save_article_images(article.url, article.images)

        discovered_count = 0

        for child_url in article.links:
            if child_url != article.url:
                mark_url_pending(child_url)
                discovered_count += 1

        mark_url_completed(url)

        # A successful crawl resets consecutive failures.
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE crawl_progress
                SET failure_count = 0, last_error = NULL
                WHERE url = ?
                """,
                (url,),
            )

        return {
            "url": url,
            "status": "completed",
            "title": article.title,
            "images": len(article.images),
            "links_discovered": discovered_count,
        }

    except Exception as exc:
        try:
            return record_failure(url, str(exc))

        except Exception as db_exc:
            print(f"[DATABASE ERROR] Could not record failure: {db_exc}")

            return {
                "url": url,
                "status": "failed",
                "error": str(exc),
            }


async def crawl_batch(
    client: httpx.AsyncClient,
    urls: list[str],
) -> list[dict]:
    """Process URLs sequentially with a delay between requests."""
    results = []

    for index, url in enumerate(urls):
        if index > 0:
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

        result = await crawl_one(client, url)
        results.append(result)

        if result["status"] == "completed":
            print(
                f"[OK] {result['title']} | "
                f"images={result['images']} | "
                f"new links={result['links_discovered']}"
            )

        elif result["status"] == "pending":
            print(
                f"[RETRY] {url} | "
                f"failures={result.get('failure_count', '?')} | "
                f"{result.get('error', '')}"
            )

        else:
            print(
                f"[FAILED] {url}: "
                f"{result.get('error', 'Unknown error')}"
            )

    return results


async def run_crawler(
    batch_size: int = BATCH_SIZE,
    max_batches: int = 5,
) -> None:
    """Discover sitemap URLs and process a bounded number of batches."""
    if batch_size < 1 or max_batches < 1:
        raise ValueError(
            "batch_size and max_batches must both be positive"
        )

    initialize_database()
    ensure_failure_count_column()

    before_articles = count_articles()

    # A failed sitemap fetch must not mark existing URLs as absent.
    sitemap_urls = await discover_urls()

    supported_urls = sorted(
        {
            clean_url
            for url in sitemap_urls
            if (clean_url := normalize_url(url)) is not None
        }
    )

    for url in supported_urls:
        mark_url_pending(url)

    print(f"Sitemap URLs discovered: {len(sitemap_urls)}")
    print(f"Supported starting pages: {len(supported_urls)}")
    print(f"Articles before run: {before_articles}")
    print(f"Batch size: {batch_size}; maximum batches: {max_batches}")
    print(f"Sitemap summary: {get_sitemap_summary()}")

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers=headers,
    ) as client:
        total_completed = 0
        total_pending_after_failure = 0
        total_terminal_failures = 0

        for batch_number in range(1, max_batches + 1):
            pending_urls = get_pending_urls(limit=batch_size)

            if not pending_urls:
                print("No pending URLs remain.")
                break

            print(
                f"\nBatch {batch_number}/{max_batches}: "
                f"{len(pending_urls)} URLs"
            )

            results = await crawl_batch(client, pending_urls)

            completed = sum(
                result["status"] == "completed"
                for result in results
            )

            retrying = sum(
                result["status"] == "pending"
                for result in results
            )

            failed = sum(
                result["status"] == "failed"
                for result in results
            )

            total_completed += completed
            total_pending_after_failure += retrying
            total_terminal_failures += failed

            print(
                f"Batch result: {completed} completed, "
                f"{retrying} scheduled for retry, "
                f"{failed} terminal failures"
            )

        print("\nCrawl run finished.")
        print(f"Completed this run: {total_completed}")
        print(f"Failures awaiting retry: {total_pending_after_failure}")
        print(f"Terminal failures this run: {total_terminal_failures}")
        print(f"Articles after run: {count_articles()}")
        print(f"Crawl progress: {count_crawl_urls()}")
        print(f"Sitemap summary: {get_sitemap_summary()}")
        print("Existing article records were preserved.")


if __name__ == "__main__":
    asyncio.run(run_crawler(batch_size=10, max_batches=5))
