"""Integration tests for ytmusic playlists router."""
import pytest


def test_list_playlists_empty(client):
    r = client.get("/music/playlists")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_get_playlist(client):
    r = client.post("/music/playlists", json={"title": "My Playlist", "description": "test desc"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert pid > 0

    r = client.get(f"/music/playlists/{pid}")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "My Playlist"
    assert data["description"] == "test desc"
    assert data["tracks"] == []


def test_update_playlist(client):
    pid = client.post("/music/playlists", json={"title": "Old"}).json()["id"]
    r = client.put(f"/music/playlists/{pid}", json={"title": "New"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert client.get(f"/music/playlists/{pid}").json()["title"] == "New"


def test_delete_playlist(client):
    pid = client.post("/music/playlists", json={"title": "Temp"}).json()["id"]
    assert client.delete(f"/music/playlists/{pid}").status_code == 200
    assert client.get(f"/music/playlists/{pid}").status_code == 404


def test_add_and_remove_track(client):
    pid = client.post("/music/playlists", json={"title": "P"}).json()["id"]
    r = client.post(f"/music/playlists/{pid}/tracks", json={
        "video_id": "abc123", "title": "Song", "duration": 180
    })
    assert r.status_code == 200
    assert r.json()["added"] is True

    pl = client.get(f"/music/playlists/{pid}").json()
    assert len(pl["tracks"]) == 1
    assert pl["tracks"][0]["video_id"] == "abc123"

    r = client.delete(f"/music/playlists/{pid}/tracks/abc123")
    assert r.status_code == 200
    assert client.get(f"/music/playlists/{pid}").json()["tracks"] == []


def test_add_duplicate_track(client):
    pid = client.post("/music/playlists", json={"title": "P"}).json()["id"]
    client.post(f"/music/playlists/{pid}/tracks", json={"video_id": "abc", "title": "T"})
    r = client.post(f"/music/playlists/{pid}/tracks", json={"video_id": "abc", "title": "T"})
    assert r.status_code == 200
    assert r.json()["added"] is False


def test_reorder_tracks(client):
    pid = client.post("/music/playlists", json={"title": "P"}).json()["id"]
    for vid, title in [("v1", "A"), ("v2", "B"), ("v3", "C")]:
        client.post(f"/music/playlists/{pid}/tracks", json={"video_id": vid, "title": title})

    r = client.post(f"/music/playlists/{pid}/order", json={"video_ids": ["v3", "v1", "v2"]})
    assert r.status_code == 200
    tracks = client.get(f"/music/playlists/{pid}").json()["tracks"]
    assert [t["video_id"] for t in tracks] == ["v3", "v1", "v2"]


def test_playlist_progress(client):
    r = client.post("/music/playlists/progress/pl-ext-123", json={
        "current_video_id": "v1",
        "current_video_title": "Song",
        "current_video_position": 45,
        "queue_index": 2,
        "total_items": 10,
    })
    assert r.status_code == 200

    r = client.get("/music/playlists/progress/pl-ext-123")
    assert r.status_code == 200
    data = r.json()
    assert data["current_video_id"] == "v1"
    assert data["queue_index"] == 2

    assert client.delete("/music/playlists/progress/pl-ext-123").status_code == 200
    data = client.get("/music/playlists/progress/pl-ext-123").json()
    assert data["queue_index"] == 0


def test_get_missing_playlist(client):
    assert client.get("/music/playlists/99999").status_code == 404
