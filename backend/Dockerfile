# AI eCommerce Mockup Generator — backend image.
#
# Built with the REPOSITORY ROOT as context (render.yaml: dockerContext=.),
# because main.py mounts the sibling frontend/ folder via a path relative to
# backend/ (BASE_DIR.parent / "frontend").
#
# Local build/run from the repo root:
#   docker build -f backend/Dockerfile -t ai-mockup-generator .
#   docker run --env-file backend/.env -p 8000:8000 ai-mockup-generator

FROM python:3.11-slim

WORKDIR /app

# Copy only the requirements file first so dependency installation is cached
# separately from application code changes.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code into /app.
COPY backend/ ./

# Copy the frontend static files to /frontend (a sibling of /app), matching
# the relative path main.py expects: BASE_DIR.parent / "frontend"
# == /app/.. /frontend == /frontend.
COPY frontend/ /frontend/

# Render sets $PORT dynamically; 8000 here is just a sensible default/doc value.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
