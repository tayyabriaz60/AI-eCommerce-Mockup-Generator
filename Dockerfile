# AI eCommerce Mockup Generator — backend image.
#
# Lives at the REPOSITORY ROOT so Render's default Docker settings work
# (Dockerfile Path = ./Dockerfile, Build Context = repo root) — including
# manually-created services that do not read render.yaml.
#
# Build context must be the repo root (not backend/) because main.py mounts
# the sibling frontend/ folder via BASE_DIR.parent / "frontend".
#
# Local build/run from the repo root:
#   docker build -t ai-mockup-generator .
#   docker run --env-file backend/.env -p 8000:8000 ai-mockup-generator

FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Frontend at /frontend (sibling of /app) — matches main.py's FRONTEND_DIR path.
COPY frontend/ /frontend/

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
