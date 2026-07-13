"""Pydantic request/response models for the mockup API."""
from datetime import datetime

from pydantic import BaseModel


class GenerateResponse(BaseModel):
    id: int
    image_url: str
    created_at: datetime


class HistoryItem(BaseModel):
    id: int
    image_url: str
    platform: str
    style: str
    product_type: str
    created_at: datetime


class HistoryResponse(BaseModel):
    items: list[HistoryItem]


class ErrorResponse(BaseModel):
    detail: str
