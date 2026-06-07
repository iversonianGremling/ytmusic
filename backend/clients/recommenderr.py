"""Thin client wrapping calls to the recommenderr service.

All external-world fetches in ytmusic route through this module so the call
site stays free of URL/auth plumbing.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

RECOMMENDERR_URL = os.environ.get("RECOMMENDERR_URL", "http://127.0.0.1:9001")
RECOMMENDERR_TOKEN = os.environ.get("RECOMMENDERR_TOKEN", "")
TIMEOUT = httpx.Timeout(15.0, connect=2.0)


def _headers() -> dict[str, str]:
    if RECOMMENDERR_TOKEN:
        return {"Authorization": f"Bearer {RECOMMENDERR_TOKEN}"}
    return {}


async def get(path: str, **params: Any) -> dict:
    async with httpx.AsyncClient(base_url=RECOMMENDERR_URL, timeout=TIMEOUT) as client:
        r = await client.get(path, params=params or None, headers=_headers())
        r.raise_for_status()
        return r.json()


async def post(path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=RECOMMENDERR_URL, timeout=TIMEOUT) as client:
        r = await client.post(path, json=json, headers=_headers())
        r.raise_for_status()
        return r.json()


# Convenience wrappers for music-side endpoints:
async def music_search(q: str, page: int = 1) -> dict:
    return await get("/v1/music/search", q=q, page=page)


async def artist(name: str) -> dict:
    return await get(f"/v1/music/artist/{name}")


async def album(album_key: str) -> dict:
    return await get(f"/v1/music/album/{album_key}")


async def recognize(video_id: str) -> dict:
    return await get(f"/v1/video/{video_id}/recognize")


async def music_recommendations(video_id: str) -> dict:
    return await get(f"/v1/music/{video_id}/recommendations")


async def radio(seeds: list[dict], limit: int = 50, diversity: float = 0.3) -> dict:
    return await post(
        "/v1/radio",
        json={"seeds": seeds, "limit": limit, "diversity": diversity},
    )


async def poll_artist_releases(artists: list[dict]) -> dict:
    return await post("/v1/artists/poll", json={"artists": artists})
