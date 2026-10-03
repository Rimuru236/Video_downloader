"""Metadata API Routes"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.metadata_service import extract_metadata
from utils.url_validator import validate_url

router = APIRouter()

class MetaRequest(BaseModel):
    url: str

@router.post("/metadata")
async def get_metadata(body: MetaRequest):
    # Validate URL before processing
    is_valid, reason = validate_url(body.url)
    if not is_valid:
        raise HTTPException(400, f"Invalid URL: {reason}")
    
    try:
        return await extract_metadata(body.url)
    except Exception as exc:
        raise HTTPException(400, str(exc))

@router.get("/metadata/formats")
async def list_formats(url: str):
    # Validate URL before processing
    is_valid, reason = validate_url(url)
    if not is_valid:
        raise HTTPException(400, f"Invalid URL: {reason}")
    
    try:
        meta = await extract_metadata(url)
        return meta.get("formats", [])
    except Exception as exc:
        raise HTTPException(400, str(exc))
