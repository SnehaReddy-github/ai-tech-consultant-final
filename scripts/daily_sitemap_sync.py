
import asyncio
import sys
from pathlib import Path

# Make the Task 1 application modules importable.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "task1-knowledge-brain" / "app"
sys.path.insert(0, str(APP_DIR))

from database import initialize_database, get_sitemap_summary
from sitemap import discover_urls


async def main() -> None:
    """Synchronize the sitemap without starting an article crawl."""
    initialize_database()

    print("Starting daily sitemap synchronization...")

    urls = await discover_urls()

    print(f"Synchronization successful: {len(urls)} URLs discovered.")
    print(f"Current sitemap summary: {get_sitemap_summary()}")
    print("No article crawl was started.")


if __name__ == "__main__":
    asyncio.run(main())
