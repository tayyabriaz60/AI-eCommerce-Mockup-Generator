"""
Storage abstraction.

For the MVP, images are saved to a local folder and served via FastAPI's
StaticFiles mount. The rest of the app only talks to `save_image()` /
`get_image_url()`, so swapping in S3/Cloudinary/etc. later only requires
changing this file.
"""
import uuid
from pathlib import Path

from config import GENERATED_DIR, STATIC_URL_PREFIX, UPLOADS_DIR


def _unique_filename(original_name: str) -> str:
    suffix = Path(original_name).suffix or ".png"
    return f"{uuid.uuid4().hex}{suffix}"


def save_upload(content: bytes, original_filename: str) -> Path:
    """Save an uploaded (input) image to local storage. Returns the saved path."""
    filename = _unique_filename(original_filename)
    dest = UPLOADS_DIR / filename
    dest.write_bytes(content)
    return dest


def save_image(content: bytes, original_filename: str = "mockup.png") -> Path:
    """Save a generated (output) image to local storage. Returns the saved path.

    This is the main function future storage backends (S3, Cloudinary, etc.)
    need to replicate: take raw bytes in, return a reference/path/URL out.
    """
    filename = _unique_filename(original_filename)
    dest = GENERATED_DIR / filename
    dest.write_bytes(content)
    return dest


def get_image_url(path: Path) -> str:
    """Convert a locally stored path into a URL the frontend can load.

    A future cloud storage backend would instead return the provider's
    public URL directly from `save_image()`, and this function could become
    a passthrough or be removed.
    """
    return f"{STATIC_URL_PREFIX}/{path.parent.name}/{path.name}"
