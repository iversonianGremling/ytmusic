"""ytmusic — album ratings router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import (
    normalize_album_key,
    get_album_rating,
    set_album_rating,
    delete_album_rating,
    get_all_album_ratings,
    upsert_album_tracks,
)

router = APIRouter(prefix="/music/ratings", tags=["ratings"])


class AlbumRatingRequest(BaseModel):
    rating: int
    album_title: str
    album_artist: str = ""
    cover_art: str = ""
    source: str = ""
    playlist_id: Optional[str] = None
    playlist_title: Optional[str] = None
    video_ids: list[str] = []


@router.get("/albums")
async def list_album_ratings(limit: int = 500):
    return get_all_album_ratings(limit)


@router.get("/albums/{album_key}")
async def get_album_rating_endpoint(album_key: str):
    result = get_album_rating(album_key)
    return result or {"rating": None}


@router.post("/albums/{album_key}")
async def set_album_rating_endpoint(album_key: str, body: AlbumRatingRequest):
    if not (1 <= body.rating <= 10):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 10")

    normalized = normalize_album_key(body.album_title, body.album_artist)
    if not normalized:
        raise HTTPException(status_code=400, detail="Album title or artist required")
    if normalized != album_key:
        raise HTTPException(status_code=400, detail="Album key mismatch")

    set_album_rating(
        normalized,
        body.album_title,
        body.album_artist,
        body.cover_art,
        body.source,
        body.playlist_id,
        body.playlist_title,
        body.rating,
    )
    if body.video_ids:
        upsert_album_tracks(
            normalized,
            body.album_title,
            body.album_artist,
            body.playlist_id,
            body.playlist_title,
            body.video_ids,
        )
    return {"ok": True, "rating": body.rating, "album": get_album_rating(normalized)}


@router.delete("/albums/{album_key}")
async def delete_album_rating_endpoint(album_key: str):
    delete_album_rating(album_key)
    return {"ok": True}
