"""ytmusic — music tags router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.db import (
    assign_tag,
    remove_tag_assignment,
    get_tags_for_video,
)
from backend.services.music_tags import (
    list_music_tag_groups,
    list_music_tags,
    create_music_tag_group,
    update_music_tag_group,
    create_music_tag,
    rename_music_tag,
    move_music_tag,
    merge_music_tag,
    delete_music_tag,
)

router = APIRouter(prefix="/music", tags=["tags"])


class TagGroupCreate(BaseModel):
    name: str


class TagGroupUpdate(BaseModel):
    name: str


class TagCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    group_id: Optional[int] = None
    kind: str = "new"


class TagMove(BaseModel):
    parent_id: Optional[int] = None
    position: int = 0
    group_id: Optional[int] = None
    kind: Optional[str] = None


class TagMerge(BaseModel):
    target_id: int
    preserve_source: bool = True


class TagRename(BaseModel):
    name: str


class TagAssignRequest(BaseModel):
    tag_id: int


@router.get("/tags")
async def get_tags():
    return {
        "groups": list_music_tag_groups(),
        "tags": list_music_tags(),
    }


@router.post("/tag-groups")
async def create_tag_group(body: TagGroupCreate):
    gid = create_music_tag_group(body.name)
    return {"id": gid}


@router.put("/tag-groups/{group_id}")
async def update_tag_group(group_id: int, body: TagGroupUpdate):
    update_music_tag_group(group_id, body.name)
    return {"ok": True}


@router.post("/tags")
async def create_tag(body: TagCreate):
    tag_id = create_music_tag(body.name, body.parent_id, body.group_id, body.kind)
    return {"id": tag_id}


@router.put("/tags/{tag_id}")
async def rename_tag(tag_id: int, body: TagRename):
    rename_music_tag(tag_id, body.name)
    return {"ok": True}


@router.post("/tags/{tag_id}/move")
async def move_tag(tag_id: int, body: TagMove):
    move_music_tag(tag_id, body.parent_id, body.position, body.group_id, body.kind)
    return {"ok": True}


@router.post("/tags/{tag_id}/merge")
async def merge_tag(tag_id: int, body: TagMerge):
    merge_music_tag(tag_id, body.target_id, body.preserve_source)
    return {"ok": True}


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int):
    delete_music_tag(tag_id)
    return {"ok": True}


@router.get("/video/{video_id}/tags")
async def get_video_tags(video_id: str):
    return get_tags_for_video(video_id)


@router.post("/video/{video_id}/tags")
async def assign_video_tag(video_id: str, body: TagAssignRequest):
    assign_tag(video_id, body.tag_id)
    return {"ok": True}


@router.delete("/video/{video_id}/tags/{tag_id}")
async def remove_video_tag(video_id: str, tag_id: int):
    remove_tag_assignment(video_id, tag_id)
    return {"ok": True}
