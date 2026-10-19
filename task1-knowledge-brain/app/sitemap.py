
import xml.etree.ElementTree as ET

import httpx

from database import sync_sitemap_urls

SITEMAP_URL = "https://support.brilliantdirectories.com/support/sitemap.xml"


async def discover_urls() -> list[str]:
    """
    Fetch and validate the complete sitemap, then synchronize its URLs.

    The database is updated only after the HTTP response succeeds and the
    XML parses into a non-empty list of URLs.
    """
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": "AI-Tech-Consultant-KnowledgeBrain/1.0"
        },
    ) as client:
        response = await client.get(SITEMAP_URL)
        response.raise_for_status()

    root = ET.fromstring(response.content)

    urls = sorted(
        {
            element.text.strip()
            for element in root.iter()
            if element.tag.endswith("loc")
            and element.text
            and element.text.strip().startswith(("https://", "http://"))
        }
    )

    if not urls:
        raise ValueError(
            "The sitemap contained no valid URLs. "
            "Existing sitemap records were not changed."
        )

    # Synchronize only after the sitemap has been fetched and validated.
    sync_sitemap_urls(urls)

    print(f"Sitemap synchronization successful: {len(urls)} URLs")
    return urls
