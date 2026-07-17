"""Routes for generating mockups and fetching generation history."""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import ALLOWED_IMAGE_CONTENT_TYPES, MAX_UPLOAD_SIZE_BYTES
from models.db import get_db
from models.schema import Generation
from schemas.mockup import (
    DeleteGenerationResponse,
    GenerateResponse,
    HistoryItem,
    HistoryResponse,
)
from services import storage
from services.hf_flux_service import HfFluxGenerationError, generate_mockup_image
from services.prompt_builder import build_prompt

logger = logging.getLogger("mockup_router")

router = APIRouter(prefix="/api", tags=["mockup"])


def _history_item(row: Generation) -> HistoryItem:
    return HistoryItem(
        id=row.id,
        image_url=storage.get_image_url(Path(row.output_image_path)),
        platform=row.platform,
        style=row.style,
        product_type=row.product_type,
        created_at=row.created_at,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_mockup(
    image: UploadFile = File(...),
    platform: str = Form(...),
    style: str = Form(...),
    product_type: str = Form(...),
    db: Session = Depends(get_db),
):
    if image.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG and JPG images are supported.")

    content = await image.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large (max 10MB).")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    # 1. Save uploaded image
    input_path = storage.save_upload(content, image.filename or "upload.png")

    # 2. Build prompt
    prompt = build_prompt(platform=platform, style=style, product_type=product_type)

    # 3. Call FLUX Kontext (image-to-image)
    try:
        result_bytes = generate_mockup_image(
            image_bytes=content, mime_type=image.content_type, prompt=prompt
        )
    except HfFluxGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 4. Save generated image
    output_path = storage.save_image(result_bytes, "mockup.png")

    # 5. Persist history row
    generation = Generation(
        platform=platform,
        style=style,
        product_type=product_type,
        input_image_path=str(input_path),
        output_image_path=str(output_path),
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)

    return GenerateResponse(
        id=generation.id,
        image_url=storage.get_image_url(output_path),
        created_at=generation.created_at,
    )


@router.get("/history", response_model=HistoryResponse)
def get_history(
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        total = db.scalar(select(func.count()).select_from(Generation)) or 0
        rows = db.execute(
            select(Generation)
            .order_by(Generation.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()

        return HistoryResponse(
            items=[_history_item(row) for row in rows],
            total=total,
        )
    except Exception as exc:
        logger.exception("Failed to fetch generation history")
        raise HTTPException(
            status_code=500,
            detail="Could not load generation history. Please try again.",
        ) from exc


@router.delete("/history/{generation_id}", response_model=DeleteGenerationResponse)
def delete_generation(generation_id: int, db: Session = Depends(get_db)):
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail=f"Generation {generation_id} not found.")

    input_path = generation.input_image_path
    output_path = generation.output_image_path

    try:
        storage.delete_image(input_path)
        storage.delete_image(output_path)
        db.delete(generation)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to delete generation %s", generation_id)
        raise HTTPException(
            status_code=500,
            detail="Could not delete this generation. Please try again.",
        ) from exc

    return DeleteGenerationResponse(success=True, id=generation_id)
