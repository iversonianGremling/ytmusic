"""ytmusic — music category recommendations (proxied to recommenderr).

The category catalog (music tag groups + tags) and the per-category recs are
owned by recommenderr's music_category_recs service. This router just forwards.
Frontend reaches these at /api/music/categories/* (nginx strips /api).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.clients import recommenderr as rec_client

router = APIRouter(prefix="/music/categories", tags=["music-categories"])


@router.get("")
@router.get("/")
async def list_music_categories():
    try:
        return await rec_client.get("/v1/music/categories")
    except Exception as exc:
        raise HTTPException(502, f"recommenderr unreachable: {exc}")


@router.get("/{kind}/{ref_id}/recommendations")
async def music_cat_recommendations(kind: str, ref_id: int, limit: int = Query(40)):
    try:
        return await rec_client.get(
            f"/v1/music/categories/{kind}/{ref_id}/recommendations", limit=limit
        )
    except Exception:
        # Keep the UI polling rather than erroring out.
        return {"status": "computing", "items": [], "last_run_at": None}


@router.post("/{kind}/{ref_id}/recompute")
async def music_cat_recompute(kind: str, ref_id: int):
    try:
        return await rec_client.post(f"/v1/music/categories/{kind}/{ref_id}/recompute")
    except Exception as exc:
        raise HTTPException(502, f"recommenderr unreachable: {exc}")
