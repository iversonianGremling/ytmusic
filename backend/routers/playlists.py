"""ytmusic — music playlists router."""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import (
    get_music_playlists,
    create_music_playlist,
    get_music_playlist,
    update_music_playlist,
    delete_music_playlist,
    add_track_to_playlist,
    remove_track_from_playlist,
    update_track_order,
    get_db,
)

router = APIRouter(prefix="/music/playlists", tags=["playlists"])


class CreatePlaylistRequest(BaseModel):
    title: str
    description: Optional[str] = ""


class UpdatePlaylistRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class AddTrackRequest(BaseModel):
    video_id: str
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    author: Optional[str] = None
    author_id: Optional[str] = None


class ReorderRequest(BaseModel):
    video_ids: list[str]


class PlaylistProgressRequest(BaseModel):
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    author: Optional[str] = None
    author_id: Optional[str] = None
    current_video_id: Optional[str] = None
    current_video_title: Optional[str] = None
    current_video_thumbnail: Optional[str] = None
    current_video_position: int
    current_video_duration: Optional[int] = None
    queue_index: int = 0
    total_items: Optional[int] = None


@router.get("")
async def list_playlists():
    return get_music_playlists()


@router.post("")
async def create_playlist(body: CreatePlaylistRequest):
    pid = create_music_playlist(body.title, body.description or "")
    return {"id": pid, "title": body.title}


@router.get("/progress/{playlist_id}")
async def get_playlist_progress(playlist_id: str):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM music_playlist_progress WHERE playlist_id=?", (playlist_id,)
        ).fetchone()
        return dict(row) if row else {"playlist_id": playlist_id, "queue_index": 0, "current_video_position": 0}
    finally:
        conn.close()


@router.post("/progress/{playlist_id}")
async def save_playlist_progress(playlist_id: str, body: PlaylistProgressRequest):
    import time
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO music_playlist_progress
                (playlist_id, title, thumbnail, author, author_id,
                 current_video_id, current_video_title, current_video_thumbnail,
                 current_video_position, current_video_duration,
                 queue_index, total_items, last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(playlist_id) DO UPDATE SET
                title=COALESCE(excluded.title, music_playlist_progress.title),
                thumbnail=COALESCE(excluded.thumbnail, music_playlist_progress.thumbnail),
                author=COALESCE(excluded.author, music_playlist_progress.author),
                author_id=COALESCE(excluded.author_id, music_playlist_progress.author_id),
                current_video_id=excluded.current_video_id,
                current_video_title=excluded.current_video_title,
                current_video_thumbnail=excluded.current_video_thumbnail,
                current_video_position=excluded.current_video_position,
                current_video_duration=excluded.current_video_duration,
                queue_index=excluded.queue_index,
                total_items=excluded.total_items,
                last_updated=excluded.last_updated
            """,
            (
                playlist_id, body.title, body.thumbnail, body.author, body.author_id,
                body.current_video_id, body.current_video_title, body.current_video_thumbnail,
                body.current_video_position, body.current_video_duration,
                body.queue_index, body.total_items, time.time(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/progress/{playlist_id}")
async def delete_playlist_progress(playlist_id: str):
    conn = get_db()
    try:
        conn.execute("DELETE FROM music_playlist_progress WHERE playlist_id=?", (playlist_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.get("/{playlist_id}")
async def get_playlist(playlist_id: int):
    pl = get_music_playlist(playlist_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return pl


@router.put("/{playlist_id}")
async def update_playlist(playlist_id: int, body: UpdatePlaylistRequest):
    update_music_playlist(playlist_id, body.title, body.description)
    return {"ok": True}


@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int):
    delete_music_playlist(playlist_id)
    return {"ok": True}


@router.post("/{playlist_id}/tracks")
async def add_track(playlist_id: int, body: AddTrackRequest):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM music_playlists WHERE id=?", (playlist_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Playlist not found")
    finally:
        conn.close()
    added = add_track_to_playlist(
        playlist_id, body.video_id, body.title or body.video_id,
        body.thumbnail, body.duration, body.author, body.author_id,
    )
    return {"ok": True, "added": added}


@router.delete("/{playlist_id}/tracks/{video_id}")
async def remove_track(playlist_id: int, video_id: str):
    remove_track_from_playlist(playlist_id, video_id)
    return {"ok": True}


@router.post("/{playlist_id}/order")
async def reorder_tracks(playlist_id: int, body: ReorderRequest):
    update_track_order(playlist_id, body.video_ids)
    return {"ok": True}
