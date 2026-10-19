
import asyncio
import ipaddress
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import URLError

import httpx
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "task1-knowledge-brain" / "app"
sys.path.insert(0, str(APP_DIR))

from database import (  # noqa: E402
    get_article_images,
    get_connection,
    initialize_database,
    save_image_description,
)
from image_ocr import extract_text_from_image  # noqa: E402

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES_PER_RUN = 25
TIMEOUT_SECONDS = 20


def is_public_https_url(url: str) -> bool:
    """Allow HTTPS image URLs with no local or private IP destination."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False

        host = parsed.hostname.lower()
        if host in {"localhost", "localhost.localdomain"}:
            return False

        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return False
        except ValueError:
            # Hostname is allowed; network access is still HTTPS-only.
            pass

        return True
    except (TypeError, ValueError):
        return False


def get_pending_images(limit: int) -> list[dict]:
    """Find image records that do not yet have extracted text."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT article_url, image_url, alt_text, caption
            FROM article_images
            WHERE TRIM(visual_description) = ''
            ORDER BY article_url, id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def download_image(url: str) -> bytes:
    """Download a bounded image response, refusing unsafe URL schemes."""
    current_url = url

    with httpx.Client(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"User-Agent": "AI-Tech-Consultant-KnowledgeBrain/1.0"},
    ) as client:
        for _ in range(5):
            if not is_public_https_url(current_url):
                raise ValueError("Image URL or redirect is not allowed.")

            with client.stream("GET", current_url) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Image redirect has no destination.")
                    from urllib.parse import urljoin
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()

                content_type = response.headers.get(
                    "content-type", ""
                ).split(";")[0].strip().lower()

                if not content_type.startswith("image/"):
                    raise ValueError("URL did not return an image.")

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds the 8 MB limit.")

                chunks = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_IMAGE_BYTES:
                        raise ValueError("Image exceeds the 8 MB limit.")
                    chunks.append(chunk)

                data = b"".join(chunks)
                if not data:
                    raise ValueError("Downloaded image is empty.")
                return data

    raise ValueError("Too many image redirects.")


def extract_text_from_bytes(data: bytes) -> dict:
    """Validate downloaded image bytes, then pass them to the OCR module."""
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "TIFF", "BMP"}:
                return {
                    "text": "",
                    "status": "error",
                    "error": "Unsupported image format.",
                }
            image.verify()

        # Use a temporary file because the existing OCR module accepts paths.
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(data)

        try:
            return extract_text_from_image(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return {
            "text": "",
            "status": "error",
            "error": f"Invalid image: {exc}",
        }


def process_images(limit: int = MAX_IMAGES_PER_RUN) -> None:
    initialize_database()
    records = get_pending_images(limit)

    print(f"Images awaiting OCR: {len(records)}")
    succeeded = 0
    failed = 0
    no_text = 0

    for index, record in enumerate(records, start=1):
        article_url = record["article_url"]
        image_url = record["image_url"]

        try:
            image_bytes = download_image(image_url)
            result = extract_text_from_bytes(image_bytes)

            if result["status"] == "success" and result["text"].strip():
                description = "OCR extracted text (may contain errors):\n"
                description += result["text"].strip()
                save_image_description(article_url, image_url, description)
                succeeded += 1
                print(f"[OCR OK] {index}/{len(records)}: {image_url}")
            elif result["status"] == "no_text_found":
                save_image_description(
                    article_url,
                    image_url,
                    "OCR processed image; no readable text found.",
                )
                no_text += 1
                print(f"[NO TEXT] {index}/{len(records)}: {image_url}")
            else:
                failed += 1
                print(
                    f"[FAILED] {index}/{len(records)}: "
                    f"{result.get('error', 'Unknown OCR error')}"
                )

        except (httpx.HTTPError, URLError, OSError, ValueError) as exc:
            failed += 1
            print(f"[FAILED] {index}/{len(records)}: {exc}")

    print("\nOCR run summary")
    print(f"Processed successfully: {succeeded}")
    print(f"No readable text: {no_text}")
    print(f"Failed (can retry): {failed}")
    print("Article text was not changed.")


if __name__ == "__main__":
    process_images()
