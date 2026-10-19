
import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from sitemap import discover_urls
from crawler import is_article_url, test_one_article
from database import (
    initialize_database,
    save_article,
    save_article_images,
    mark_url_pending,
    get_pending_urls,
    mark_url_completed,
    mark_url_failed,
    count_crawl_urls,
)

BATCH_SIZE = 3
REQUEST_DELAY_SECONDS = 1.0


async def main() -> None:
    initialize_database()

    print("Reading support sitemap...")
    urls = await discover_urls()
    article_urls = sorted({
        url for url in urls if is_article_url(url)
    })

    print(f"URLs discovered in sitemap: {len(urls)}")
    print(f"Individual articles found: {len(article_urls)}")

    # Register discovered URLs without resetting existing progress.
    for url in article_urls:
        mark_url_pending(url)

    batch = get_pending_urls(limit=BATCH_SIZE)

    if not batch:
        print("No pending URLs to process.")
        print("Crawl progress:", count_crawl_urls())
        return

    added = updated = unchanged = failed = 0
    total_images = 0

    for index, url in enumerate(batch):
        if index > 0:
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

        try:
            print(f"\nFetching ({index + 1}/{len(batch)}): {url}")
            article = await test_one_article(url)

            result = save_article(
                url=article.url,
                title=article.title,
                content=article.content,
            )

            # Store images linked to their original article.
            image_count = save_article_images(
                article_url=article.url,
                images=article.images,
            )
            total_images += image_count

            mark_url_completed(url)

            print(f"Title: {article.title}")
            print(f"Database result: {result}")
            print(f"Images saved: {image_count}")

            if result == "added":
                added += 1
            elif result == "updated":
                updated += 1
            elif result == "unchanged":
                unchanged += 1

        except Exception as error:
            failed += 1
            mark_url_failed(url, str(error))
            print(f"Failed to ingest {url}: {error}")

    print("\n--- Ingestion Summary ---")
    print(f"Added: {added}")
    print(f"Updated: {updated}")
    print(f"Unchanged: {unchanged}")
    print(f"Failed: {failed}")
    print(f"Image references saved: {total_images}")
    print("Crawl progress:", count_crawl_urls())


if __name__ == "__main__":
    asyncio.run(main())
