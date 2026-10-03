from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from database.db_manager import get_session
from core.queue_manager import get_queue_manager

router = APIRouter()

class QueueAdd(BaseModel):
    download_id: str
    priority: int = 5

class ReorderBody(BaseModel):
    download_id: str
    new_position: int

@router.get("/queue")
async def list_queue():
    return await get_queue_manager().list_queue()

@router.post("/queue/add")
async def add_to_queue(body: QueueAdd):
    item = await get_queue_manager().add(body.download_id, body.priority)
    return {"queue_id": item.id, "position": item.position}

@router.post("/queue/start")
async def start_queue():
    await get_queue_manager().resume()
    return {"status": "started"}

@router.post("/queue/pause")
async def pause_queue():
    await get_queue_manager().pause()
    return {"status": "paused"}

@router.post("/queue/clear")
async def clear_queue():
    await get_queue_manager().clear()
    return {"status": "cleared"}

@router.post("/queue/reorder")
async def reorder(body: ReorderBody):
    await get_queue_manager().reorder(body.download_id, body.new_position)
    return {"status": "reordered"}

@router.delete("/queue/{download_id}")
async def remove_from_queue(download_id: str):
    await get_queue_manager().remove(download_id)
    return {"removed": True}
