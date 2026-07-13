# AI eCommerce Mockup Generator (MVP)

Upload a product design (t-shirt graphic, mug design, poster art, etc.), pick a marketplace + mockup style, and get back an AI-generated, realistic product mockup — powered by Google's Gemini image generation model (`gemini-2.5-flash-image`, aka "nano banana").

**Flow:** upload → choose options → generate → preview/download. Anonymous, global "Recent Generations" history (last 10) is saved to Postgres.

## Tech Stack

- **Frontend:** Plain HTML + CSS + Vanilla JS (no build step) — `frontend/`
- **Backend:** Python + FastAPI — `backend/`
- **AI:** Google Gemini via the `google-genai` SDK
- **Database:** PostgreSQL (SQLAlchemy + psycopg2), falls back to local SQLite if `DATABASE_URL` isn't set
- **Storage:** Local disk for MVP, served via FastAPI static files, abstracted behind `services/storage.py` so a real cloud provider (S3, Cloudinary, etc.) can be swapped in later
- **Deployment:** Render (single Web Service serves both the API and the static frontend)

## Project Structure

```
backend/
  main.py                  # FastAPI app, CORS, static mounts, routers
  config.py                # centralized env-driven configuration
  routers/mockup.py         # POST /api/generate, GET /api/history
  services/
    gemini_service.py       # Gemini API wrapper
    storage.py              # save/serve image abstraction (local for MVP)
    prompt_builder.py       # builds the Gemini prompt
  models/
    db.py                   # SQLAlchemy engine/session
    schema.py                # Generation table
  schemas/mockup.py          # Pydantic request/response models
  static/generated/          # generated mockups (gitignored, kept via .gitkeep)
  static/uploads/            # uploaded source images (gitignored, kept via .gitkeep)
  requirements.txt
  .env.example
frontend/
  index.html
  style.css
  app.js
render.yaml
```

## Local Setup

### 1. Prerequisites

- Python 3.11+
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey))
- (Optional for local dev) PostgreSQL — if you skip this, the app falls back to a local SQLite file so you can develop without installing Postgres.

### 2. Configure environment variables

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

```
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash-image
DATABASE_URL=postgresql://user:password@host:port/dbname   # or leave unset to use local SQLite
PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 3. Install dependencies

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux
pip install -r requirements.txt
```

### 4. Run the app

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — FastAPI serves the `frontend/` folder directly, so this single URL gives you the full app (no separate frontend server needed). The `generations` table is created automatically on startup.

### 5. Try it

1. Upload a PNG/JPG design.
2. Pick a marketplace, mockup style, and product type.
3. Click **Generate Mockup** and wait for the Gemini-generated result.
4. Download the result, or check the "Recent Generations" grid at the bottom.

## API Reference

### `POST /api/generate`

`multipart/form-data`:

| field | type | description |
|---|---|---|
| `image` | file | PNG or JPG, max 10MB |
| `platform` | string | `Etsy`, `Shopify`, `Amazon`, `TikTok Shop`, `Custom` |
| `style` | string | `White Background`, `Studio Lighting`, `Lifestyle Scene`, `Flat Lay`, `Minimalist` |
| `product_type` | string | `T-shirt`, `Mug`, `Poster/Wall Art`, `Phone Case`, `Tote Bag`, `Sticker`, `Other` |

Response:

```json
{ "id": 1, "image_url": "/static/generated/abcd1234.png", "created_at": "2026-07-13T12:00:00Z" }
```

Errors (safety block, quota exceeded, invalid image, etc.) return a `4xx` with a friendly `{"detail": "..."}` message instead of a raw stack trace.

### `GET /api/history`

Returns the last 10 generations:

```json
{ "items": [{ "id": 1, "image_url": "...", "platform": "Etsy", "style": "Studio Lighting", "product_type": "Mug", "created_at": "..." }] }
```

### `GET /api/health`

Simple health check → `{"status": "ok"}`.

## Deploying to Render

This repo includes a `render.yaml` (Render "Blueprint") that provisions:

- **`ai-mockup-generator`** — a Web Service running the FastAPI backend (which also serves the frontend static files, so this is the only service you need).
- **`ai-mockup-db`** — a managed Render Postgres instance, wired into the web service via `DATABASE_URL`.

### Steps

1. Push this repo to GitHub.
2. In the Render dashboard: **New → Blueprint**, point it at your repo. Render will read `render.yaml` and provision both services.
3. Set the `GEMINI_API_KEY` environment variable on the web service (marked `sync: false` in `render.yaml`, so Render will prompt for it rather than storing it in the blueprint).
4. Deploy. Render will run:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Once live, visit the service URL — it serves both the app UI and the API from one origin.

### Manual setup (without `render.yaml`)

1. Create a **Postgres** instance on Render, copy its connection string.
2. Create a **Web Service**, root directory `backend/`, build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Add env vars: `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL` (from step 1), `CORS_ORIGINS`.

## Notes on MVP Scope & Future Extensions

This is intentionally scoped tight. Things deliberately left out (and where to add them later):

- **Auth / user accounts** — history is currently global/anonymous. Add a `user_id` column to `generations` + an auth layer when needed.
- **Cloud storage (S3/Cloudinary/etc.)** — `services/storage.py` is the only place that touches the filesystem. Swap `save_image()`/`save_upload()` internals to upload to a provider and return its URL; nothing else needs to change.
- **Batch processing / multi-image export** — out of scope; the single-flow endpoint would need to become async/queued to support this.
- **Marketplace-specific dimension rules & auto product-type detection** — `prompt_builder.py` and the product type `<select>` are the natural extension points.
