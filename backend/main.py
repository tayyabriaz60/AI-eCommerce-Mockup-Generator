"""FastAPI application entrypoint: app setup, CORS, static mounts, routers."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR, CORS_ORIGINS, GENERATED_DIR, UPLOADS_DIR
from models.db import init_db
from routers import mockup

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI eCommerce Mockup Generator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# --- API routes ---
app.include_router(mockup.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# --- Static file mounts ---
# Uploaded/generated images (served from backend/static/*)
app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")

# Frontend (plain HTML/CSS/JS) — mounted last so it doesn't shadow /api routes.
# Single Render service: backend serves the frontend directly at "/".
FRONTEND_DIR = BASE_DIR.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"status": "ok", "message": "Frontend not found; API is running."}
