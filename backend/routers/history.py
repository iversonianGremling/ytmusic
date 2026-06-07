"""ytmusic — watch history and progress router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.db import (
    add_music_history,
    get_music_history,
    delete_music_history_item,
    clear_music_history,
    save_music_progress,
    get_music_progress,
    delete_music_progress,
    get_continue_watching_music,
    get_music_stats,
)

router = APIRouter(tags=["history"])


class HistoryRequest(BaseModel):
    video_id: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    author: Optional[str] = None
    author_id: Optional[str] = None


class WatchProgressRequest(BaseModel):
    position: int
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    author: Optional[str] = None
    author_id: Optional[str] = None


@router.post("/music/history")
async def history_add(body: HistoryRequest):
    add_music_history(body.video_id, body.title, body.thumbnail, body.duration, body.author, body.author_id)
    return {"ok": True}


@router.get("/music/history")
async def history_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return get_music_history(limit, offset)


@router.delete("/music/history")
async def history_clear():
    clear_music_history()
    return {"ok": True}


@router.delete("/music/history/{video_id}")
async def history_remove(video_id: str):
    delete_music_history_item(video_id)
    return {"ok": True}


@router.post("/music/history/{video_id}/progress")
async def save_progress(video_id: str, body: WatchProgressRequest):
    save_music_progress(
        video_id, body.title, body.thumbnail, body.duration, body.author, body.author_id, body.position
    )
    return {"ok": True}


@router.get("/music/history/{video_id}/progress")
async def get_progress(video_id: str):
    p = get_music_progress(video_id)
    return p if p else {"video_id": video_id, "position": 0}


@router.delete("/music/history/{video_id}/progress")
async def remove_progress(video_id: str):
    delete_music_progress(video_id)
    return {"ok": True}


@router.get("/music/continue-listening")
async def continue_listening(limit: int = Query(20, ge=1, le=50)):
    return get_continue_watching_music(limit)


@router.get("/music/stats")
async def music_stats(limit: int = Query(6, ge=1, le=24)):
    return get_music_stats(limit)
