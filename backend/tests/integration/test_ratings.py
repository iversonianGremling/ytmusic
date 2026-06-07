"""Integration tests for ytmusic ratings router."""
import pytest


ALBUM_KEY = "test artist::test album"


def test_album_rating_lifecycle(client):
    r = client.get(f"/music/ratings/albums/{ALBUM_KEY}")
    assert r.status_code == 200
    assert r.json()["rating"] is None

    r = client.post(f"/music/ratings/albums/{ALBUM_KEY}", json={
        "rating": 8,
        "album_title": "Test Album",
        "album_artist": "Test Artist",
        "cover_art": "https://example.com/cover.jpg",
        "source": "bandcamp",
    })
    assert r.status_code == 200
    assert r.json()["rating"] == 8

    r = client.get(f"/music/ratings/albums/{ALBUM_KEY}")
    assert r.status_code == 200
    data = r.json()
    assert data["rating"] == 8
    assert data["album_title"] == "Test Album"

    assert client.delete(f"/music/ratings/albums/{ALBUM_KEY}").status_code == 200
    assert client.get(f"/music/ratings/albums/{ALBUM_KEY}").json()["rating"] is None


def test_album_rating_with_tracks(client):
    r = client.post(f"/music/ratings/albums/{ALBUM_KEY}", json={
        "rating": 9,
        "album_title": "Test Album",
        "album_artist": "Test Artist",
        "video_ids": ["v1", "v2", "v3"],
    })
    assert r.status_code == 200


def test_album_rating_validation(client):
    r = client.post(f"/music/ratings/albums/{ALBUM_KEY}", json={
        "rating": 11,
        "album_title": "T",
        "album_artist": "A",
    })
    assert r.status_code == 400

    r = client.post(f"/music/ratings/albums/{ALBUM_KEY}", json={
        "rating": 5,
        "album_title": "",
        "album_artist": "",
    })
    assert r.status_code == 400


def test_list_album_ratings(client):
    client.post(f"/music/ratings/albums/{ALBUM_KEY}", json={
        "rating": 7, "album_title": "Test Album", "album_artist": "Test Artist"
    })
    r = client.get("/music/ratings/albums")
    assert r.status_code == 200
    assert len(r.json()) >= 1
