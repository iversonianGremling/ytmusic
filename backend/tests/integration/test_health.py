def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "ytmusic"
    assert body["status"] == "ok"
    assert body["schema_version"] == 1


def test_schema_applied(tmp_db):
    import sqlite3

    con = sqlite3.connect(tmp_db)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    names = {r[0] for r in rows}
    expected_subset = {
        "music_playlists",
        "music_playlist_tracks",
        "watch_history",
        "watch_progress",
        "album_ratings",
        "album_tracks",
        "artist_follows",
        "music_tags",
        "music_tag_groups",
        "music_tag_assignments",
    }
    assert expected_subset.issubset(names), names
