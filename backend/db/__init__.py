"""ytmusic DB layer — owns music-mode user state.

Tables owned: album_ratings, album_tracks, artist_follows, music_tags,
music_tag_groups, music_tag_assignments, music_playlists,
music_playlist_tracks, watch_history, watch_progress.
"""
from __future__ import annotations

import os
import re
import sqlite3
import time

DB_PATH = os.environ.get("DB_PATH", "/opt/ytmusic/data/ytmusic.db")


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db() -> sqlite3.Connection:
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Key normalisation ─────────────────────────────────────────────────────────

def _norm_token(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_album_key(album_title: str | None, album_artist: str | None = None) -> str:
    title = _norm_token(album_title)
    artist = _norm_token(album_artist)
    if title and artist:
        return f"{artist}::{title}"
    return title or artist


def normalize_artist_key(artist_name: str | None) -> str:
    return _norm_token(artist_name)


# ── Album ratings ─────────────────────────────────────────────────────────────

def get_album_rating(album_key: str):
    if not album_key:
        return None
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT album_key, album_title, album_artist, cover_art, source,
                   playlist_id, playlist_title, CAST(rating AS INTEGER) AS rating, rated_at
            FROM album_ratings
            WHERE album_key = ?
            """,
            (album_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_album_rating(
    album_key: str,
    album_title: str,
    album_artist: str,
    cover_art: str,
    source: str,
    playlist_id: str | None,
    playlist_title: str | None,
    rating: int,
):
    if not album_key:
        return
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO album_ratings
                (album_key, album_title, album_artist, cover_art, source,
                 playlist_id, playlist_title, rating, rated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                album_key,
                album_title,
                album_artist,
                cover_art,
                source,
                playlist_id,
                playlist_title,
                int(rating),
                time.time(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_album_rating(album_key: str):
    if not album_key:
        return
    conn = get_db()
    try:
        conn.execute("DELETE FROM album_ratings WHERE album_key = ?", (album_key,))
        conn.commit()
    finally:
        conn.close()


def get_all_album_ratings(limit: int = 500) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM album_ratings ORDER BY rated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def upsert_album_tracks(
    album_key: str,
    album_title: str,
    album_artist: str,
    playlist_id: str | None,
    playlist_title: str | None,
    video_ids: list[str],
):
    if not album_key or not video_ids:
        return
    conn = get_db()
    try:
        now = time.time()
        for index, video_id in enumerate(video_ids):
            conn.execute(
                """
                INSERT INTO album_tracks
                    (video_id, album_key, album_title, album_artist, playlist_id, playlist_title,
                     track_index, added_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(video_id) DO UPDATE SET
                    album_key=excluded.album_key,
                    album_title=excluded.album_title,
                    album_artist=excluded.album_artist,
                    playlist_id=excluded.playlist_id,
                    playlist_title=excluded.playlist_title,
                    track_index=excluded.track_index,
                    added_at=excluded.added_at
                """,
                (video_id, album_key, album_title, album_artist, playlist_id, playlist_title, index, now),
            )
        conn.commit()
    finally:
        conn.close()


# ── Artist follows ─────────────────────────────────────────────────────────────

def get_artist_follow(artist_name: str):
    artist_key = normalize_artist_key(artist_name)
    if not artist_key:
        return None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM artist_follows WHERE artist_key = ?",
            (artist_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_artist_follow_state(artist_name: str) -> bool:
    return get_artist_follow(artist_name) is not None


def get_artist_follows(limit: int = 100) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT * FROM artist_follows
            ORDER BY updated_at DESC, artist_name COLLATE NOCASE ASC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def follow_artist(
    artist_name: str,
    *,
    image: str | None = None,
    source: str | None = None,
    spotify_artist_id: str | None = None,
    deezer_artist_id: str | None = None,
    itunes_artist_id: str | None = None,
):
    artist_key = normalize_artist_key(artist_name)
    if not artist_key:
        return None

    existing = get_artist_follow(artist_name)
    now = time.time()
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO artist_follows (
                artist_key, artist_name, image, source,
                spotify_artist_id, deezer_artist_id, itunes_artist_id,
                last_release_key, last_release_title, last_release_date,
                last_release_cover_art, last_release_source,
                last_checked_at, created_at, updated_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(artist_key) DO UPDATE SET
                artist_name=excluded.artist_name,
                image=COALESCE(NULLIF(excluded.image, ''), artist_follows.image),
                source=COALESCE(NULLIF(excluded.source, ''), artist_follows.source),
                spotify_artist_id=COALESCE(NULLIF(excluded.spotify_artist_id, ''), artist_follows.spotify_artist_id),
                deezer_artist_id=COALESCE(NULLIF(excluded.deezer_artist_id, ''), artist_follows.deezer_artist_id),
                itunes_artist_id=COALESCE(NULLIF(excluded.itunes_artist_id, ''), artist_follows.itunes_artist_id),
                last_release_key=COALESCE(excluded.last_release_key, artist_follows.last_release_key),
                last_release_title=COALESCE(excluded.last_release_title, artist_follows.last_release_title),
                last_release_date=COALESCE(excluded.last_release_date, artist_follows.last_release_date),
                last_release_cover_art=COALESCE(excluded.last_release_cover_art, artist_follows.last_release_cover_art),
                last_release_source=COALESCE(excluded.last_release_source, artist_follows.last_release_source),
                last_checked_at=COALESCE(excluded.last_checked_at, artist_follows.last_checked_at),
                updated_at=excluded.updated_at
            """,
            (
                artist_key,
                artist_name.strip(),
                image or (existing or {}).get("image"),
                source or (existing or {}).get("source"),
                spotify_artist_id or (existing or {}).get("spotify_artist_id"),
                deezer_artist_id or (existing or {}).get("deezer_artist_id"),
                itunes_artist_id or (existing or {}).get("itunes_artist_id"),
                (existing or {}).get("last_release_key"),
                (existing or {}).get("last_release_title"),
                (existing or {}).get("last_release_date"),
                (existing or {}).get("last_release_cover_art"),
                (existing or {}).get("last_release_source"),
                (existing or {}).get("last_checked_at"),
                (existing or {}).get("created_at") or now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_artist_follow(artist_name)


def unfollow_artist(artist_name: str):
    artist_key = normalize_artist_key(artist_name)
    if not artist_key:
        return
    conn = get_db()
    try:
        conn.execute("DELETE FROM artist_follows WHERE artist_key = ?", (artist_key,))
        conn.commit()
    finally:
        conn.close()


def sync_follows_from_ratings(min_rating: int = 8) -> dict:
    min_rating = max(1, min(10, int(min_rating)))
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT TRIM(album_artist) AS artist_name
            FROM album_ratings
            WHERE rating >= ? AND album_artist IS NOT NULL AND TRIM(album_artist) != ''
            """,
            (min_rating,),
        ).fetchall()
    finally:
        conn.close()
    added = 0
    already_following = 0
    for row in rows:
        name = (row["artist_name"] or "").strip()
        if not name:
            continue
        if get_artist_follow(name):
            already_following += 1
            continue
        follow_artist(name)
        added += 1
    return {
        "added": added,
        "already_following": already_following,
        "distinct_artists": len(rows),
    }


# ── Music tags ────────────────────────────────────────────────────────────────

def get_music_tags(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Return all music tags as flat list with group info."""
    _close = conn is None
    if conn is None:
        conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT mt.id, mt.name, mt.kind, mt.group_id, mt.parent_id, mt.position,
                   g.name AS group_name, g.system_key AS group_system_key
            FROM music_tags mt
            LEFT JOIN music_tag_groups g ON g.id = mt.group_id
            ORDER BY COALESCE(g.position, 0) ASC, mt.position ASC, mt.id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if _close:
            conn.close()


def create_music_tag(name: str, parent_id: int | None = None, group_id: int | None = None, kind: str = "new") -> int:
    from backend.services.music_tags import create_music_tag as _create
    return _create(name, parent_id, group_id, kind)


def update_music_tag(tag_id: int, name: str) -> None:
    from backend.services.music_tags import rename_music_tag as _rename
    _rename(tag_id, name)


def delete_music_tag(tag_id: int) -> None:
    from backend.services.music_tags import delete_music_tag as _delete
    _delete(tag_id)


def create_tag_group(name: str) -> int:
    from backend.services.music_tags import create_music_tag_group as _create
    return _create(name)


def update_tag_group(group_id: int, name: str) -> None:
    from backend.services.music_tags import update_music_tag_group as _update
    _update(group_id, name)


def move_tag(tag_id: int, parent_id: int | None, position: int, group_id: int | None = None, kind: str | None = None):
    from backend.services.music_tags import move_music_tag as _move
    _move(tag_id, parent_id, position, group_id, kind)


def merge_tags(source_id: int, target_id: int, preserve_source: bool):
    from backend.services.music_tags import merge_music_tag as _merge
    _merge(source_id, target_id, preserve_source)


# ── Music tag assignments ─────────────────────────────────────────────────────

def get_tags_for_video(video_id: str, per_video_limit: int = 12) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT mta.tag_id AS tag_id, mt.name AS tag_name, g.name AS group_name
            FROM music_tag_assignments mta
            JOIN music_tags mt ON mt.id = mta.tag_id
            LEFT JOIN music_tag_groups g ON g.id = mt.group_id
            WHERE mta.video_id = ?
            ORDER BY mt.name COLLATE NOCASE
            LIMIT ?
            """,
            (video_id, per_video_limit),
        ).fetchall()
        return [
            {"id": int(r["tag_id"]), "name": r["tag_name"], "group_name": r["group_name"]}
            for r in rows
        ]
    finally:
        conn.close()


def assign_tag(video_id: str, tag_id: int) -> None:
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO music_tag_assignments (tag_id, video_id, created_at) VALUES (?,?,?)",
            (tag_id, video_id, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def remove_tag_assignment(video_id: str, tag_id: int) -> None:
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM music_tag_assignments WHERE tag_id=? AND video_id=?",
            (tag_id, video_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Music playlists ────────────────────────────────────────────────────────────

def get_music_playlists() -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT p.*, COUNT(t.id) AS track_count,
                   (SELECT t2.thumbnail FROM music_playlist_tracks t2
                    WHERE t2.playlist_id=p.id ORDER BY t2.position LIMIT 1) AS first_thumb
            FROM music_playlists p
            LEFT JOIN music_playlist_tracks t ON t.playlist_id=p.id
            GROUP BY p.id
            ORDER BY p.updated_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_music_playlist(title: str, description: str = "") -> int:
    conn = get_db()
    try:
        now = time.time()
        row = conn.execute(
            "INSERT INTO music_playlists (title, description, created_at, updated_at) VALUES (?,?,?,?)",
            (title, description, now, now),
        )
        pid = row.lastrowid
        conn.commit()
        return int(pid)
    finally:
        conn.close()


def get_music_playlist(playlist_id: int) -> dict | None:
    conn = get_db()
    try:
        pl = conn.execute("SELECT * FROM music_playlists WHERE id=?", (playlist_id,)).fetchone()
        if not pl:
            return None
        tracks = conn.execute(
            "SELECT * FROM music_playlist_tracks WHERE playlist_id=? ORDER BY position ASC",
            (playlist_id,),
        ).fetchall()
        result = dict(pl)
        result["tracks"] = [dict(t) for t in tracks]
        return result
    finally:
        conn.close()


def update_music_playlist(playlist_id: int, title: str | None = None, description: str | None = None):
    conn = get_db()
    try:
        now = time.time()
        if title is not None:
            conn.execute(
                "UPDATE music_playlists SET title=?, updated_at=? WHERE id=?",
                (title, now, playlist_id),
            )
        if description is not None:
            conn.execute(
                "UPDATE music_playlists SET description=?, updated_at=? WHERE id=?",
                (description, now, playlist_id),
            )
        conn.commit()
    finally:
        conn.close()


def delete_music_playlist(playlist_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM music_playlists WHERE id=?", (playlist_id,))
        conn.commit()
    finally:
        conn.close()


def add_track_to_playlist(
    playlist_id: int,
    video_id: str,
    title: str,
    thumbnail: str | None = None,
    duration: int | None = None,
    author: str | None = None,
    author_id: str | None = None,
    source_managed: int = 0,
) -> bool:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT MAX(position) AS mx FROM music_playlist_tracks WHERE playlist_id=?",
            (playlist_id,),
        ).fetchone()
        pos = (row["mx"] or 0) + 1
        now = time.time()
        try:
            conn.execute(
                """
                INSERT INTO music_playlist_tracks
                    (playlist_id, video_id, title, thumbnail, duration, author, author_id, position, added_at, source_managed)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (playlist_id, video_id, title, thumbnail, duration, author, author_id, pos, now, source_managed),
            )
            conn.execute("UPDATE music_playlists SET updated_at=? WHERE id=?", (now, playlist_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            return False
    finally:
        conn.close()


def remove_track_from_playlist(playlist_id: int, video_id: str):
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM music_playlist_tracks WHERE playlist_id=? AND video_id=?",
            (playlist_id, video_id),
        )
        conn.execute(
            "UPDATE music_playlists SET updated_at=? WHERE id=?",
            (time.time(), playlist_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_playlist_tracks(playlist_id: int) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM music_playlist_tracks WHERE playlist_id=? ORDER BY position ASC",
            (playlist_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_track_order(playlist_id: int, video_ids: list[str]) -> None:
    conn = get_db()
    try:
        for idx, video_id in enumerate(video_ids):
            conn.execute(
                "UPDATE music_playlist_tracks SET position=? WHERE playlist_id=? AND video_id=?",
                (idx, playlist_id, video_id),
            )
        conn.execute(
            "UPDATE music_playlists SET updated_at=? WHERE id=?",
            (time.time(), playlist_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Watch history (music mode) ─────────────────────────────────────────────────

def add_music_history(
    video_id: str,
    title: str,
    thumbnail: str | None = None,
    duration: int | None = None,
    author: str | None = None,
    author_id: str | None = None,
):
    conn = get_db()
    try:
        now = time.time()
        conn.execute(
            """
            INSERT INTO watch_history (video_id, title, thumbnail, duration, author, author_id,
                                       watched_at, listen_count, first_listened_at)
            VALUES (?,?,?,?,?,?,?,1,?)
            ON CONFLICT(video_id) DO UPDATE SET
                title=excluded.title,
                thumbnail=excluded.thumbnail,
                duration=excluded.duration,
                author=excluded.author,
                author_id=excluded.author_id,
                listen_count=COALESCE(watch_history.listen_count, 1) + 1,
                first_listened_at=COALESCE(watch_history.first_listened_at, excluded.first_listened_at),
                watched_at=excluded.watched_at
            """,
            (video_id, title, thumbnail, duration, author, author_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_music_history(limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM watch_history ORDER BY watched_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_music_history_item(video_id: str):
    conn = get_db()
    try:
        conn.execute("DELETE FROM watch_history WHERE video_id=?", (video_id,))
        conn.commit()
    finally:
        conn.close()


def clear_music_history():
    conn = get_db()
    try:
        conn.execute("DELETE FROM watch_history")
        conn.commit()
    finally:
        conn.close()


# ── Watch progress (music mode) ────────────────────────────────────────────────

def save_music_progress(
    video_id: str,
    title: str | None,
    thumbnail: str | None,
    duration: int | None,
    author: str | None,
    author_id: str | None,
    position: int,
):
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO watch_progress
                (video_id, title, thumbnail, duration, author, author_id, position, last_updated, media_type)
            VALUES (?,?,?,?,?,?,?,?,'music')
            ON CONFLICT(video_id) DO UPDATE SET
                title=COALESCE(excluded.title, watch_progress.title),
                thumbnail=COALESCE(excluded.thumbnail, watch_progress.thumbnail),
                duration=COALESCE(excluded.duration, watch_progress.duration),
                author=COALESCE(excluded.author, watch_progress.author),
                author_id=COALESCE(excluded.author_id, watch_progress.author_id),
                position=excluded.position,
                last_updated=excluded.last_updated
            """,
            (video_id, title, thumbnail, duration, author, author_id, position, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_music_progress(video_id: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM watch_progress WHERE video_id=?", (video_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_music_progress(video_id: str):
    conn = get_db()
    try:
        conn.execute("DELETE FROM watch_progress WHERE video_id=?", (video_id,))
        conn.commit()
    finally:
        conn.close()


def get_continue_watching_music(limit: int = 20) -> list[dict]:
    """Partially-played music tracks."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT * FROM watch_progress
            WHERE position > 30
              AND (duration IS NULL OR position < duration - 30)
              AND media_type = 'music'
            ORDER BY last_updated DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Music stats ────────────────────────────────────────────────────────────────

def get_music_stats(limit: int = 6) -> dict:
    conn = get_db()
    try:
        top_tracks = [dict(r) for r in conn.execute(
            """
            SELECT video_id, title, author AS artist, thumbnail,
                   COALESCE(listen_count, 1) AS listens, watched_at AS last_played
            FROM watch_history
            ORDER BY listens DESC, watched_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()]
        top_artists = [dict(r) for r in conn.execute(
            """
            SELECT author AS artist,
                   SUM(COALESCE(listen_count, 1)) AS listens,
                   COUNT(DISTINCT video_id) AS track_count,
                   MAX(watched_at) AS last_played
            FROM watch_history
            WHERE author IS NOT NULL AND TRIM(author) != ''
            GROUP BY author
            ORDER BY listens DESC, last_played DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()]
        return {
            "top_tracks": top_tracks,
            "top_artists": top_artists,
        }
    finally:
        conn.close()
