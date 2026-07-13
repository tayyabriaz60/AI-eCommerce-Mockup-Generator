"""Routes for generating mockups and fetching generation history."""
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import ALLOWED_IMAGE_CONTENT_TYPES, MAX_UPLOAD_SIZE_BYTES
from models.db import get_db
from models.schema import Generation
from schemas.mockup import GenerateResponse, HistoryItem, HistoryResponse
from services import storage
from services.gemini_service import GeminiGenerationError, generate_mockup_image
from services.prompt_builder import build_prompt

logger = logging.getLogger("mockup_router")

router = APIRouter(prefix="/api", tags=["mockup"])


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

    # 3. Call Gemini (image-to-image)
    try:
        result_bytes = generate_mockup_image(
            image_bytes=content, mime_type=image.content_type, prompt=prompt
        )
    except GeminiGenerationError as exc:
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
def get_history(db: Session = Depends(get_db)):
    from pathlib import Path

    rows = db.execute(
        select(Generation).order_by(Generation.created_at.desc()).limit(10)
    ).scalars().all()

    items = [
        HistoryItem(
            id=row.id,
            image_url=storage.get_image_url(Path(row.output_image_path)),
            platform=row.platform,
            style=row.style,
            product_type=row.product_type,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return HistoryResponse(items=items)
