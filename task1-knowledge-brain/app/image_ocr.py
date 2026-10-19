
import os
import re
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError

# Windows Tesseract installation path.
DEFAULT_TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if Path(DEFAULT_TESSERACT_PATH).is_file():
    pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_PATH


def extract_text_from_image(image_path: str | Path) -> dict:
    """
    Extract visible text from an image using local Tesseract OCR.

    Returns a dictionary containing extracted text, status, and
    an error message if processing fails.
    """
    path = Path(image_path)

    if not path.is_file():
        return {
            "text": "",
            "status": "error",
            "error": "Image file does not exist.",
        }

    try:
        # Limit image size to reduce memory usage.
        with Image.open(path) as original:
            if original.format not in {
                "PNG", "JPEG", "WEBP", "TIFF", "BMP"
            }:
                return {
                    "text": "",
                    "status": "error",
                    "error": "Unsupported image format.",
                }

            image = ImageOps.exif_transpose(original)
            image.load()

            # Convert to grayscale and enlarge small screenshots.
            image = ImageOps.grayscale(image)
            if image.width < 1200:
                scale = min(2, 1200 / max(image.width, 1))
                image = image.resize(
                    (
                        int(image.width * scale),
                        int(image.height * scale),
                    )
                )

            # OCR runs locally; no image is sent to an external service.
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6",
                timeout=30,
            )

        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        return {
            "text": text,
            "status": "success" if text else "no_text_found",
            "error": None,
        }

    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return {
            "text": "",
            "status": "error",
            "error": f"Could not read image: {exc}",
        }
    except pytesseract.TesseractNotFoundError:
        return {
            "text": "",
            "status": "error",
            "error": "Tesseract OCR executable was not found.",
        }
    except RuntimeError as exc:
        return {
            "text": "",
            "status": "error",
            "error": f"OCR processing failed or timed out: {exc}",
        }
