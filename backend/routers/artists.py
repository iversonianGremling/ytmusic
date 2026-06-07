"""ytmusic — artist follows router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.db import (
    get_artist_follow,
    get_artist_follows,
    follow_artist,
    unfollow_artist,
    sync_follows_from_ratings,
)
from backend.clients import recommenderr as rec_client

router = APIRouter(prefix="/music", tags=["artists"])


class ArtistFollowRequest(BaseModel):
    name: Optional[str] = None
    image: Optional[str] = None
    source: Optional[str] = None
    spotify_artist_id: Optional[str] = None
    deezer_artist_id: Optional[str] = None
    itunes_artist_id: Optional[str] = None


@router.get("/follows/artists")
async def list_followed_artists(limit: int = Query(24, ge=1, le=200)):
    artists = get_artist_follows(limit)
    releases: list = []
    try:
        data = await rec_client.poll_artist_releases(artists)
        releases = data.get("releases", [])
    except Exception:
        pass
    return {"artists": artists, "releases": releases}


@router.post("/follows/artists/sync-from-ratings")
async def sync_follows_from_album_ratings(min_rating: int = Query(8, ge=1, le=10)):
    stats = sync_follows_from_ratings(min_rating)
    return {"ok": True, **stats}


@router.get("/artist/{artist_name}/follow")
async def artist_follow_state(artist_name: str):
    follow = get_artist_follow(artist_name)
    return {"followed": bool(follow), "artist": follow}


@router.post("/artist/{artist_name}/follow")
async def follow_artist_endpoint(artist_name: str, body: ArtistFollowRequest):
    resolved = (body.name or artist_name).strip()
    if not resolved:
        raise HTTPException(status_code=422, detail="Artist name is required")
    follow_artist(
        resolved,
        image=body.image,
        source=body.source,
        spotify_artist_id=body.spotify_artist_id,
        deezer_artist_id=body.deezer_artist_id,
        itunes_artist_id=body.itunes_artist_id,
    )
    artist = get_artist_follow(resolved)
    return {"followed": True, "artist": artist}


@router.delete("/artist/{artist_name}/follow")
async def unfollow_artist_endpoint(artist_name: str):
    unfollow_artist(artist_name)
    return {"ok": True}
