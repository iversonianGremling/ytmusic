"""Integration tests for ytmusic history router."""
import pytest


def test_history_add_and_list(client):
    r = client.post("/music/history", json={
        "video_id": "v1", "title": "Track 1", "author": "Artist", "duration": 200
    })
    assert r.status_code == 200

    r = client.get("/music/history")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["video_id"] == "v1"
    assert items[0]["listen_count"] == 1


def test_history_listen_count_increments(client):
    for _ in range(3):
        client.post("/music/history", json={"video_id": "v2", "title": "T"})
    items = client.get("/music/history").json()
    track = next(x for x in items if x["video_id"] == "v2")
    assert track["listen_count"] == 3


def test_history_remove_item(client):
    client.post("/music/history", json={"video_id": "v3", "title": "T"})
    assert client.delete("/music/history/v3").status_code == 200
    items = client.get("/music/history").json()
    assert not any(x["video_id"] == "v3" for x in items)


def test_history_clear(client):
    for vid in ["a", "b", "c"]:
        client.post("/music/history", json={"video_id": vid, "title": vid})
    assert client.delete("/music/history").status_code == 200
    assert client.get("/music/history").json() == []


def test_watch_progress_save_get_delete(client):
    r = client.post("/music/history/v4/progress", json={
        "position": 90, "title": "T", "duration": 300
    })
    assert r.status_code == 200

    r = client.get("/music/history/v4/progress")
    assert r.status_code == 200
    assert r.json()["position"] == 90

    assert client.delete("/music/history/v4/progress").status_code == 200
    r = client.get("/music/history/v4/progress")
    assert r.json()["position"] == 0


def test_progress_missing_returns_zero(client):
    r = client.get("/music/history/doesnotexist/progress")
    assert r.status_code == 200
    assert r.json()["position"] == 0


def test_continue_listening(client):
    client.post("/music/history/v5/progress", json={"position": 60, "duration": 300})
    r = client.get("/music/continue-listening")
    assert r.status_code == 200
    items = r.json()
    assert any(x["video_id"] == "v5" for x in items)


def test_stats(client):
    client.post("/music/history", json={"video_id": "s1", "title": "T", "author": "A"})
    r = client.get("/music/stats")
    assert r.status_code == 200
    data = r.json()
    assert "top_tracks" in data
    assert "top_artists" in data
