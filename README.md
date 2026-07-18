# AI eCommerce Mockup Generator (MVP)

Upload a product design (t-shirt graphic, mug design, poster art, etc.), pick a marketplace + mockup style, and get back an AI-generated, realistic product mockup — powered by Hugging Face's public **FLUX.1 Kontext Dev** ZeroGPU Space (`black-forest-labs/FLUX.1-Kontext-dev`).

**Flow:** upload → choose options → generate → preview/download. Anonymous, global "Recent Generations" history (last 10) is saved to Postgres.

## Tech Stack

- **Frontend:** Plain HTML + CSS + Vanilla JS (no build step) — `frontend/`
- **Backend:** Python + FastAPI — `backend/`
- **AI:** Free public Hugging Face ZeroGPU Space — FLUX.1 Kontext Dev via `gradio_client` (no Inference Providers billing)
- **Database:** PostgreSQL (SQLAlchemy + psycopg2), falls back to local SQLite if `DATABASE_URL` isn't set
- **Storage:** Local disk for MVP, served via FastAPI static files, abstracted behind `services/storage.py` so a real cloud provider (S3, Cloudinary, etc.) can be swapped in later
- **Deployment:** Render (single Web Service serves both the API and the static frontend)

## Free ZeroGPU vs paid APIs

This MVP calls the **public community Space** on Hugging Face's free ZeroGPU hardware. That means:

- **No billing / no credit card** for basic use — unlike Hugging Face Inference Providers or fal.ai routing.
- **Shared compute** — requests may sit in a queue, cold starts can take 30–120+ seconds, and the Space can occasionally be down or rate-limited.
- **Optional `HF_API_TOKEN`** — anonymous access works; a logged-in HF token uses your account's higher free ZeroGPU daily minute allowance.
- **License:** FLUX.1 Kontext Dev is **non-commercial**. This setup is for **prototyping / MVP validation**, not paid production use without a proper commercial license from [Black Forest Labs](https://blackforestlabs.ai/).

## Project Structure

```
backend/
  main.py                  # FastAPI app, CORS, static mounts, routers
  config.py                # centralized env-driven configuration
  routers/mockup.py         # POST /api/generate, GET /api/history
  services/
    hf_flux_service.py      # Hugging Face ZeroGPU Space wrapper (gradio_client)
    storage.py              # save/serve image abstraction (local for MVP)
    prompt_builder.py       # builds the Kontext editing prompt
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
Dockerfile                    # at repo root — Render's default Docker path (see Render section)
.dockerignore                 # at repo root (Docker build context root)
render.yaml
```

## Local Setup

### 1. Prerequisites

- Python 3.11+
- (Optional) A Hugging Face access token for a higher free ZeroGPU quota ([Hugging Face settings](https://huggingface.co/settings/tokens))
- Accept the FLUX.1 Kontext Dev model license on its [model page](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev) if you use an authenticated token
- (Optional for local dev) PostgreSQL — if you skip this, the app falls back to a local SQLite file so you can develop without installing Postgres.

### 2. Configure environment variables

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` (see [Environment Variables](#environment-variables) below). `HF_API_TOKEN` can be left blank for anonymous ZeroGPU access.

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

On first generation, the server logs the Space's Gradio API endpoints (from `view_api()`) so you can verify the `/infer` signature if anything changes upstream.

### 5. Try it

1. Upload a PNG/JPG design.
2. Pick a marketplace, mockup style, and product type.
3. Click **Generate Mockup** and wait — ZeroGPU queue + generation can take **1–2 minutes**.
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

Errors (queue busy, Space down, invalid image, etc.) return a `4xx` with a friendly `{"detail": "..."}` message instead of a raw stack trace.

### `GET /api/history`

Returns paginated generations (`?limit=12&offset=0`):

```json
{ "items": [{ "id": 1, "image_url": "...", "platform": "Etsy", "style": "Studio Lighting", "product_type": "Mug", "created_at": "..." }], "total": 1 }
```

### `GET /api/health`

Simple health check → `{"status": "ok"}`.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `HF_API_TOKEN` | No | — | Optional Hugging Face token. Anonymous ZeroGPU works without it; a token increases your free daily ZeroGPU quota. |
| `HF_MODEL` | No | `black-forest-labs/FLUX.1-Kontext-dev` | Hugging Face **Space repo id** (not a paid Inference Providers model id). |
| `HF_SPACE_TIMEOUT_SECONDS` | No | `120` | Max seconds to wait in the ZeroGPU queue plus generation before returning a "busy" error. |
| `DATABASE_URL` | No (Render: auto) | `sqlite:///./local.db` | PostgreSQL connection string. Render Blueprint wires this from the managed Postgres instance. |
| `PORT` | No | `8000` | Server port. Render sets this automatically in production. |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:8000` | Comma-separated allowed origins for local dev CORS. |

Example `backend/.env`:

```
DATABASE_URL=
HF_API_TOKEN=
HF_MODEL=black-forest-labs/FLUX.1-Kontext-dev
HF_SPACE_TIMEOUT_SECONDS=120
PORT=8000
```

The app starts without `HF_API_TOKEN` and logs a warning suggesting you add one for a higher free daily quota.

## Deploying to Render (Docker)

This repo includes a `render.yaml` (Render "Blueprint") that provisions:

- **`ai-mockup-generator`** — a Docker-based Web Service running the FastAPI backend (which also serves the frontend static files, so this is the only service you need).
- **`ai-mockup-db`** — a managed Render Postgres instance, wired into the web service via `DATABASE_URL`.

The service uses `runtime: docker`, `dockerfilePath: ./Dockerfile`, and `dockerContext: .` (repo root). The Dockerfile lives at the **repository root** (not inside `backend/`) because Render's default Docker settings — and manually-created services that never read `render.yaml` — look for `./Dockerfile` at the repo root. The build context must also be the repo root so the Docker build can include both `backend/` and the sibling `frontend/` folder (`main.py` mounts it via `BASE_DIR.parent / "frontend"`).

### Steps

1. Push this repo to GitHub.
2. In the Render dashboard: **New → Blueprint**, point it at your repo. Render will read `render.yaml`, build the Docker image, and provision both services.
3. **Optionally add `HF_API_TOKEN`** in the web service's **Environment** tab for a higher free ZeroGPU quota. It is marked `sync: false` in `render.yaml` — not required for anonymous access.
4. Confirm `HF_MODEL` is set (defaults to `black-forest-labs/FLUX.1-Kontext-dev` via `render.yaml`) and that `DATABASE_URL` is wired to your Postgres instance.
5. Deploy. Render builds from the root `Dockerfile` and runs `uvicorn main:app --host 0.0.0.0 --port $PORT`.
6. Once live, visit the service URL — it serves both the app UI and the API from one origin.

> **ZeroGPU note:** The first request after idle may wait in a shared queue for **30–120+ seconds**. This is expected on free community hardware, not a bug. If you see "The free AI model is busy right now", wait a minute and retry. Increase `HF_SPACE_TIMEOUT_SECONDS` if your queue waits are longer than 120s.

If you use an authenticated HF token, accept the FLUX.1 Kontext Dev license on its [model page](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev) (one-time, tied to your HF account).

### Building/running the Docker image locally

Run these from the **repo root**, since the build context must include both `backend/` and the sibling `frontend/` folder:

```bash
docker build -t ai-mockup-generator .
docker run --env-file backend/.env -p 8000:8000 ai-mockup-generator
```

Then open http://localhost:8000.

### Manual setup in the Render dashboard (without `render.yaml`)

1. Create a **Postgres** instance on Render, copy its connection string.
2. Create a **Web Service**, set **Language/Runtime** to **Docker**. Leave **Dockerfile Path** as the default (`./Dockerfile`) and **Docker Build Context Directory** as the repo root (`.`).
3. Add env vars: `HF_MODEL`, `HF_SPACE_TIMEOUT_SECONDS`, `DATABASE_URL`, `CORS_ORIGINS`, and optionally `HF_API_TOKEN`.

Remove any old `HF_PROVIDER` / `HF_BILL_TO` vars from previous Inference Providers deployments — they are no longer used.

### Alternative: native Python runtime (no Docker)

If you'd rather not use Docker, Render also supports a native Python runtime: set `rootDir: backend`, build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`. This repo is set up for the Docker path by default, but nothing about the app code is Docker-specific, so switching back is just a `render.yaml`/dashboard config change.

## Notes on MVP Scope & Future Extensions

This is intentionally scoped tight. Things deliberately left out (and where to add them later):

- **Auth / user accounts** — history is currently global/anonymous. Add a `user_id` column to `generations` + an auth layer when needed.
- **Cloud storage (S3/Cloudinary/etc.)** — `services/storage.py` is the only place that touches the filesystem. Swap `save_image()`/`save_upload()` internals to upload to a provider and return its URL; nothing else needs to change.
- **Batch processing / multi-image export** — out of scope; the single-flow endpoint would need to become async/queued to support this.
- **Marketplace-specific dimension rules & auto product-type detection** — `prompt_builder.py` and the product type `<select>` are the natural extension points.
- **Production-grade AI** — swap `hf_flux_service.py` to a paid Inference Provider, fal.ai direct, or self-hosted FLUX when you outgrow free ZeroGPU limits or need commercial licensing.
