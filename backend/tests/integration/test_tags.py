"""Integration tests for ytmusic tags router."""
import pytest


def test_get_tags_empty(client):
    r = client.get("/music/tags")
    assert r.status_code == 200
    data = r.json()
    assert "groups" in data
    assert "tags" in data


def test_create_tag_group_and_tag(client):
    r = client.post("/music/tag-groups", json={"name": "Moods"})
    assert r.status_code == 200
    gid = r.json()["id"]
    assert gid > 0

    r = client.post("/music/tags", json={"name": "Happy", "group_id": gid, "kind": "existing"})
    assert r.status_code == 200
    tid = r.json()["id"]
    assert tid > 0

    tags = client.get("/music/tags").json()
    tag_ids = [n["id"] for n in tags["tags"]]
    assert tid in tag_ids


def test_rename_tag(client):
    tid = client.post("/music/tags", json={"name": "Old Name"}).json()["id"]
    r = client.put(f"/music/tags/{tid}", json={"name": "New Name"})
    assert r.status_code == 200
    tags = client.get("/music/tags").json()
    names = {n["id"]: n["name"] for n in _flatten(tags["tags"])}
    assert names[tid] == "New Name"


def test_delete_tag(client):
    tid = client.post("/music/tags", json={"name": "ToDelete"}).json()["id"]
    assert client.delete(f"/music/tags/{tid}").status_code == 200
    tags = client.get("/music/tags").json()
    tag_ids = [n["id"] for n in _flatten(tags["tags"])]
    assert tid not in tag_ids


def test_video_tag_assign_and_remove(client):
    tid = client.post("/music/tags", json={"name": "Chill"}).json()["id"]
    vid = "videoabc123"

    r = client.post(f"/music/video/{vid}/tags", json={"tag_id": tid})
    assert r.status_code == 200

    r = client.get(f"/music/video/{vid}/tags")
    assert r.status_code == 200
    assert any(t["id"] == tid for t in r.json())

    assert client.delete(f"/music/video/{vid}/tags/{tid}").status_code == 200
    r = client.get(f"/music/video/{vid}/tags")
    assert not any(t["id"] == tid for t in r.json())


def test_merge_tags_preserve_source(client):
    src = client.post("/music/tags", json={"name": "Src"}).json()["id"]
    dst = client.post("/music/tags", json={"name": "Dst"}).json()["id"]
    r = client.post(f"/music/tags/{src}/merge", json={"target_id": dst, "preserve_source": True})
    assert r.status_code == 200


def _flatten(nodes: list) -> list:
    result = []
    for n in nodes:
        result.append(n)
        result.extend(_flatten(n.get("children", [])))
    return result
