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

# --- Gemini / AI config ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image").strip()

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
