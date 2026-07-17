"""
Centralized app configuration, loaded from environment variables.

Keeping all env-driven settings in one place makes it easy to extend later
(e.g. swap storage providers, change model names, add new platforms) without
hunting through business logic for hardcoded values.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- Hugging Face / AI config ---
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "").strip()
HF_MODEL = os.getenv("HF_MODEL", "black-forest-labs/FLUX.1-Kontext-dev").strip()
# FLUX Kontext is served via HF Inference Providers (fal), not legacy serverless API.
HF_PROVIDER = os.getenv("HF_PROVIDER", "fal-ai").strip()


def validate_config() -> None:
    """Fail fast at startup if required configuration is missing."""
    if not HF_API_TOKEN:
        raise RuntimeError(
            "HF_API_TOKEN is not set. Add your Hugging Face access token to the "
            "environment (see .env.example). On Render, paste it in the service's "
            "Environment tab."
        )
    if not HF_MODEL:
        raise RuntimeError(
            "HF_MODEL is not set. Default is black-forest-labs/FLUX.1-Kontext-dev."
        )

# --- Database ---
# .strip() guards against trailing newlines/whitespace that can sneak in when
# a connection string is copy-pasted into a dashboard env var field — psycopg2
# will otherwise try to connect to a database literally named "...\n".
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db").strip()

# --- Server ---
PORT = int(os.getenv("PORT", "8000"))

# --- CORS ---
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
    if origin.strip()
]

# --- Storage (local MVP storage, swappable later behind storage.py) ---
GENERATED_DIR = BASE_DIR / "static" / "generated"
UPLOADS_DIR = BASE_DIR / "static" / "uploads"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Public URL prefix under which /static is mounted in main.py
STATIC_URL_PREFIX = "/static"

# --- Domain option lists (kept here so frontend/backend can stay in sync) ---
PLATFORMS = ["Etsy", "Shopify", "Amazon", "TikTok Shop", "Custom"]
STYLES = ["White Background", "Studio Lighting", "Lifestyle Scene", "Flat Lay", "Minimalist"]
PRODUCT_TYPES = ["T-shirt", "Mug", "Poster/Wall Art", "Phone Case", "Tote Bag", "Sticker", "Other"]

ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
