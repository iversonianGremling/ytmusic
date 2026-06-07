"""Music tag service for ytmusic.

Ported from the monolith's services/music_tags.py, adapted to use ytmusic's
own DB (music_playlists / music_playlist_tracks instead of playlists /
playlist_videos, and no music_library cross-reference).
"""
from __future__ import annotations

import time

from fastapi import HTTPException

from backend.db import get_db

DEFAULT_GROUPS = {
    "existing": "Existing tags",
    "new": "New tags",
}
DEFAULT_GROUP_ORDER = ["existing", "new"]
VALID_TAG_KINDS = set(DEFAULT_GROUPS)


def _normalize_group_name(name: str | None) -> str:
    clean = " ".join((name or "").split())
    if not clean:
        raise HTTPException(status_code=422, detail="Music meta-tag name is required")
    return clean


def _normalize_tag_kind(kind: str | None, fallback: str | None = None) -> str:
    candidate = (kind or fallback or "existing").strip().lower()
    if candidate not in VALID_TAG_KINDS:
        raise HTTPException(status_code=422, detail="Music tag kind must be 'existing' or 'new'")
    return candidate


def _ensure_default_group(conn, system_key: str) -> int:
    normalized_key = _normalize_tag_kind(system_key)
    row = conn.execute(
        "SELECT id FROM music_tag_groups WHERE system_key=?", (normalized_key,)
    ).fetchone()
    if row:
        return int(row["id"])
    now = time.time()
    group_id = conn.execute(
        """
        INSERT INTO music_tag_groups (name, system_key, position, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            DEFAULT_GROUPS[normalized_key],
            normalized_key,
            DEFAULT_GROUP_ORDER.index(normalized_key),
            now,
            now,
        ),
    ).lastrowid
    return int(group_id)


def _ensure_default_groups(conn) -> dict[str, int]:
    return {key: _ensure_default_group(conn, key) for key in DEFAULT_GROUP_ORDER}


def _resolve_group_id(
    conn,
    group_id: int | None = None,
    legacy_kind: str | None = None,
    fallback_system_key: str = "existing",
) -> int:
    if group_id is not None:
        row = conn.execute("SELECT id FROM music_tag_groups WHERE id=?", (group_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Music meta-tag not found")
        return int(row["id"])
    return _ensure_default_group(conn, _normalize_tag_kind(legacy_kind, fallback_system_key))


def _legacy_kind_for_group(conn, group_id: int, fallback: str = "existing") -> str:
    row = conn.execute(
        "SELECT system_key FROM music_tag_groups WHERE id=?", (group_id,)
    ).fetchone()
    if row and row["system_key"] in VALID_TAG_KINDS:
        return str(row["system_key"])
    return _normalize_tag_kind(fallback)


def _next_group_position(conn) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM music_tag_groups"
    ).fetchone()
    return int(row[0] or 0)


def _next_position(conn, parent_id: int | None, group_id: int | None = None) -> int:
    if parent_id is None:
        if group_id is None:
            raise HTTPException(status_code=422, detail="Target meta-tag is required for root tags")
        row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM music_tags WHERE parent_id IS NULL AND group_id=?",
            (group_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM music_tags WHERE parent_id=?",
            (parent_id,),
        ).fetchone()
    return int(row[0] or 0)


def _ordered_sibling_ids(
    conn,
    parent_id: int | None,
    group_id: int | None = None,
    exclude_id: int | None = None,
) -> list[int]:
    if parent_id is None:
        if group_id is None:
            raise HTTPException(status_code=422, detail="Target meta-tag is required for root tags")
        rows = conn.execute(
            """
            SELECT id FROM music_tags
            WHERE parent_id IS NULL AND group_id=? AND (? IS NULL OR id != ?)
            ORDER BY position ASC, id ASC
            """,
            (group_id, exclude_id, exclude_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id FROM music_tags
            WHERE parent_id=? AND (? IS NULL OR id != ?)
            ORDER BY position ASC, id ASC
            """,
            (parent_id, exclude_id, exclude_id),
        ).fetchall()
    return [int(r["id"]) for r in rows]


def _renumber_parent(conn, parent_id: int | None, group_id: int | None = None):
    for index, tag_id in enumerate(_ordered_sibling_ids(conn, parent_id, group_id)):
        conn.execute("UPDATE music_tags SET position=? WHERE id=?", (index, tag_id))


def get_music_tag_descendant_ids(conn, tag_id: int) -> list[int]:
    rows = conn.execute(
        """
        WITH RECURSIVE descendants(id) AS (
            SELECT id FROM music_tags WHERE id=?
            UNION ALL
            SELECT mt.id FROM music_tags mt JOIN descendants d ON mt.parent_id = d.id
        )
        SELECT id FROM descendants
        """,
        (tag_id,),
    ).fetchall()
    return [int(r["id"]) for r in rows]


def _set_subtree_group(conn, tag_id: int, group_id: int):
    descendant_ids = get_music_tag_descendant_ids(conn, tag_id)
    if not descendant_ids:
        return
    placeholders = ",".join("?" for _ in descendant_ids)
    now = time.time()
    legacy_kind = _legacy_kind_for_group(conn, group_id)
    conn.execute(
        f"UPDATE music_tags SET group_id=?, kind=?, updated_at=? WHERE id IN ({placeholders})",
        [group_id, legacy_kind, now, *descendant_ids],
    )


def _move_tag(conn, tag_id, parent_id, position, group_id=None, kind=None):
    row = conn.execute(
        "SELECT id, parent_id, group_id, kind FROM music_tags WHERE id=?", (tag_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Music tag not found")

    current_parent_id = int(row["parent_id"]) if row["parent_id"] is not None else None
    current_group_id = (
        int(row["group_id"])
        if row["group_id"] is not None
        else _resolve_group_id(conn, legacy_kind=row["kind"], fallback_system_key="existing")
    )
    current_kind = _normalize_tag_kind(row["kind"], "existing")

    if parent_id == tag_id:
        raise HTTPException(status_code=422, detail="Tag cannot become its own parent")

    if parent_id is not None:
        parent = conn.execute(
            "SELECT id, group_id FROM music_tags WHERE id=?", (parent_id,)
        ).fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Target parent not found")
        descendants = set(get_music_tag_descendant_ids(conn, tag_id))
        if parent_id in descendants:
            raise HTTPException(status_code=422, detail="Cannot move a tag into its own subtree")
        target_group_id = int(parent["group_id"]) if parent["group_id"] is not None else current_group_id
    else:
        if group_id is None and kind is None:
            target_group_id = current_group_id
        else:
            target_group_id = _resolve_group_id(
                conn, group_id=group_id, legacy_kind=kind, fallback_system_key=current_kind
            )

    sibling_ids = _ordered_sibling_ids(
        conn, parent_id, target_group_id if parent_id is None else None, exclude_id=tag_id
    )
    insert_at = max(0, min(position, len(sibling_ids)))
    sibling_ids.insert(insert_at, tag_id)

    now = time.time()
    target_kind = _legacy_kind_for_group(conn, target_group_id, current_kind)
    for index, sibling_id in enumerate(sibling_ids):
        if sibling_id == tag_id:
            conn.execute(
                "UPDATE music_tags SET parent_id=?, group_id=?, position=?, kind=?, updated_at=? WHERE id=?",
                (parent_id, target_group_id, index, target_kind, now, sibling_id),
            )
        else:
            conn.execute(
                "UPDATE music_tags SET parent_id=?, position=?, updated_at=? WHERE id=?",
                (parent_id, index, now, sibling_id),
            )

    if target_group_id != current_group_id:
        _set_subtree_group(conn, tag_id, target_group_id)

    if current_parent_id is None:
        if current_group_id != target_group_id or parent_id is not None:
            _renumber_parent(conn, None, current_group_id)
    elif current_parent_id != parent_id:
        _renumber_parent(conn, current_parent_id)


def _ensure_playlist_tag(conn, playlist_id: int, playlist_title: str | None) -> int:
    link = conn.execute(
        "SELECT tag_id FROM music_tag_playlist_links WHERE playlist_id=?", (playlist_id,)
    ).fetchone()
    if link:
        tag = conn.execute("SELECT id FROM music_tags WHERE id=?", (link["tag_id"],)).fetchone()
        if tag:
            return int(tag["id"])
        conn.execute("DELETE FROM music_tag_playlist_links WHERE playlist_id=?", (playlist_id,))

    default_group_id = _ensure_default_group(conn, "existing")
    now = time.time()
    tag_id = conn.execute(
        """
        INSERT INTO music_tags (name, kind, group_id, parent_id, position, created_at, updated_at)
        VALUES (?, 'existing', ?, NULL, ?, ?, ?)
        """,
        (
            (playlist_title or "").strip() or f"Playlist {playlist_id}",
            default_group_id,
            _next_position(conn, None, default_group_id),
            now,
            now,
        ),
    ).lastrowid
    conn.execute(
        "INSERT INTO music_tag_playlist_links (playlist_id, tag_id, created_at, updated_at) VALUES (?,?,?,?)",
        (playlist_id, tag_id, now, now),
    )
    return int(tag_id)


def _sync_tag_playlist_assignments(conn, tag_id: int | None = None):
    """Assign tags to tracks that are in linked playlists."""
    params: list = [time.time()]
    where = ""
    if tag_id is not None:
        where = "WHERE l.tag_id = ?"
        params.append(tag_id)
    conn.execute(
        f"""
        INSERT OR IGNORE INTO music_tag_assignments (tag_id, video_id, created_at)
        SELECT DISTINCT l.tag_id, pt.video_id, ?
        FROM music_tag_playlist_links l
        JOIN music_playlist_tracks pt ON pt.playlist_id = l.playlist_id
        {where}
        """,
        params,
    )


def _ensure_all_playlist_tags(conn):
    _ensure_default_groups(conn)
    rows = conn.execute(
        "SELECT id, title FROM music_playlists ORDER BY created_at ASC"
    ).fetchall()
    for row in rows:
        _ensure_playlist_tag(conn, int(row["id"]), row["title"])


# ── Public API ─────────────────────────────────────────────────────────────────

def list_music_tag_groups() -> list[dict]:
    conn = get_db()
    try:
        _ensure_default_groups(conn)
        conn.commit()
        rows = conn.execute(
            """
            SELECT g.id, g.name, g.system_key, g.position,
                   COALESCE(s.root_count, 0) AS root_count,
                   COALESCE(s.tag_count, 0) AS tag_count
            FROM music_tag_groups g
            LEFT JOIN (
                SELECT group_id,
                       COUNT(*) AS tag_count,
                       SUM(CASE WHEN parent_id IS NULL THEN 1 ELSE 0 END) AS root_count
                FROM music_tags GROUP BY group_id
            ) s ON s.group_id = g.id
            ORDER BY g.position ASC, g.id ASC
            """
        ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "name": r["name"],
                "system_key": r["system_key"],
                "position": int(r["position"]),
                "root_count": int(r["root_count"] or 0),
                "tag_count": int(r["tag_count"] or 0),
            }
            for r in rows
        ]
    finally:
        conn.close()


def list_music_tags() -> list[dict]:
    conn = get_db()
    try:
        default_group_ids = _ensure_default_groups(conn)
        _ensure_all_playlist_tags(conn)
        _sync_tag_playlist_assignments(conn)
        conn.commit()
        rows = conn.execute(
            """
            SELECT mt.id, mt.name, mt.kind, mt.group_id,
                   g.name AS group_name, g.system_key AS group_system_key, g.position AS group_position,
                   mt.parent_id, mt.position,
                   COALESCE(COUNT(DISTINCT mta.video_id), 0) AS direct_item_count
            FROM music_tags mt
            LEFT JOIN music_tag_groups g ON g.id = mt.group_id
            LEFT JOIN music_tag_assignments mta ON mta.tag_id = mt.id
            GROUP BY mt.id
            ORDER BY COALESCE(g.position, 0) ASC, mt.position ASC, mt.id ASC
            """
        ).fetchall()
        playlist_count_rows = conn.execute(
            "SELECT tag_id, COUNT(*) AS c FROM music_tag_playlist_links GROUP BY tag_id"
        ).fetchall()
    finally:
        conn.close()

    playlist_counts = {int(r["tag_id"]): int(r["c"]) for r in playlist_count_rows}
    nodes: dict[int, dict] = {}
    for row in rows:
        legacy_kind = _normalize_tag_kind(row["kind"], row["group_system_key"] or "existing")
        group_id = (
            int(row["group_id"])
            if row["group_id"] is not None
            else default_group_ids.get(legacy_kind, default_group_ids["existing"])
        )
        group_name = row["group_name"] or DEFAULT_GROUPS.get(legacy_kind, DEFAULT_GROUPS["existing"])
        nodes[int(row["id"])] = {
            "id": int(row["id"]),
            "name": row["name"],
            "kind": legacy_kind,
            "group_id": group_id,
            "group_name": group_name,
            "group_system_key": row["group_system_key"],
            "parent_id": int(row["parent_id"]) if row["parent_id"] is not None else None,
            "position": int(row["position"]),
            "direct_item_count": int(row["direct_item_count"] or 0),
            "item_count": int(row["direct_item_count"] or 0),
            "playlist_count": playlist_counts.get(int(row["id"]), 0),
            "children": [],
            "_group_position": int(row["group_position"] or 0),
        }

    roots: list[dict] = []
    for node in nodes.values():
        pid = node["parent_id"]
        if pid is None or pid not in nodes:
            roots.append(node)
        else:
            nodes[pid]["children"].append(node)

    def finalize(node: dict) -> int:
        node["children"].sort(key=lambda c: (c["position"], c["name"].lower(), c["id"]))
        total = node["direct_item_count"]
        for child in node["children"]:
            total += finalize(child)
        node["item_count"] = total
        node.pop("_group_position", None)
        return total

    roots.sort(key=lambda n: (n["_group_position"], n["position"], n["name"].lower(), n["id"]))
    for root in roots:
        finalize(root)
    return roots


def create_music_tag_group(name: str) -> int:
    clean = _normalize_group_name(name)
    conn = get_db()
    try:
        _ensure_default_groups(conn)
        if conn.execute(
            "SELECT id FROM music_tag_groups WHERE lower(name)=lower(?)", (clean,)
        ).fetchone():
            raise HTTPException(status_code=422, detail="Music meta-tag name already exists")
        now = time.time()
        gid = conn.execute(
            "INSERT INTO music_tag_groups (name, system_key, position, created_at, updated_at) VALUES (?,NULL,?,?,?)",
            (clean, _next_group_position(conn), now, now),
        ).lastrowid
        conn.commit()
        return int(gid)
    finally:
        conn.close()


def update_music_tag_group(group_id: int, name: str):
    clean = _normalize_group_name(name)
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM music_tag_groups WHERE id=?", (group_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Music meta-tag not found")
        if conn.execute(
            "SELECT id FROM music_tag_groups WHERE lower(name)=lower(?) AND id != ?", (clean, group_id)
        ).fetchone():
            raise HTTPException(status_code=422, detail="Music meta-tag name already exists")
        conn.execute(
            "UPDATE music_tag_groups SET name=?, updated_at=? WHERE id=?", (clean, time.time(), group_id)
        )
        conn.commit()
    finally:
        conn.close()


def create_music_tag(
    name: str,
    parent_id: int | None = None,
    group_id: int | None = None,
    kind: str = "new",
) -> int:
    clean = " ".join((name or "").split())
    if not clean:
        raise HTTPException(status_code=422, detail="Music tag name is required")
    conn = get_db()
    try:
        _ensure_default_groups(conn)
        target_group_id = _resolve_group_id(conn, group_id=group_id, legacy_kind=kind, fallback_system_key="new")
        if parent_id is not None:
            parent = conn.execute("SELECT id, group_id FROM music_tags WHERE id=?", (parent_id,)).fetchone()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent music tag not found")
            target_group_id = int(parent["group_id"]) if parent["group_id"] is not None else target_group_id
        now = time.time()
        tag_id = conn.execute(
            "INSERT INTO music_tags (name, kind, group_id, parent_id, position, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                clean,
                _legacy_kind_for_group(conn, target_group_id, kind),
                target_group_id,
                parent_id,
                _next_position(conn, parent_id, target_group_id),
                now,
                now,
            ),
        ).lastrowid
        conn.commit()
        return int(tag_id)
    finally:
        conn.close()


def rename_music_tag(tag_id: int, name: str):
    clean = " ".join((name or "").split())
    if not clean:
        raise HTTPException(status_code=422, detail="Tag name cannot be empty")
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM music_tags WHERE id=?", (tag_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Music tag not found")
        conn.execute("UPDATE music_tags SET name=?, updated_at=? WHERE id=?", (clean, time.time(), tag_id))
        conn.commit()
    finally:
        conn.close()


def move_music_tag(tag_id, parent_id, position, group_id=None, kind=None):
    conn = get_db()
    try:
        _move_tag(conn, tag_id, parent_id, position, group_id, kind)
        conn.commit()
    finally:
        conn.close()


def merge_music_tag(source_id: int, target_id: int, preserve_source: bool):
    if source_id == target_id:
        raise HTTPException(status_code=422, detail="Choose a different target tag")
    conn = get_db()
    try:
        _ensure_default_groups(conn)
        source = conn.execute(
            "SELECT id, parent_id, group_id, kind FROM music_tags WHERE id=?", (source_id,)
        ).fetchone()
        target = conn.execute(
            "SELECT id, group_id FROM music_tags WHERE id=?", (target_id,)
        ).fetchone()
        if not source or not target:
            raise HTTPException(status_code=404, detail="Music tag not found")

        descendants = set(get_music_tag_descendant_ids(conn, source_id))
        if target_id in descendants:
            raise HTTPException(status_code=422, detail="Cannot merge into a descendant tag")

        if preserve_source:
            _move_tag(conn, source_id, target_id, _next_position(conn, target_id))
            conn.commit()
            return

        source_group_id = (
            int(source["group_id"])
            if source["group_id"] is not None
            else _resolve_group_id(conn, legacy_kind=source["kind"], fallback_system_key="existing")
        )
        target_group_id = (
            int(target["group_id"]) if target["group_id"] is not None else source_group_id
        )
        now = time.time()
        target_kind = _legacy_kind_for_group(conn, target_group_id, "existing")
        source_children = _ordered_sibling_ids(conn, source_id)
        next_pos = _next_position(conn, target_id)
        for child_id in source_children:
            conn.execute(
                "UPDATE music_tags SET parent_id=?, position=?, group_id=?, kind=?, updated_at=? WHERE id=?",
                (target_id, next_pos, target_group_id, target_kind, now, child_id),
            )
            _set_subtree_group(conn, child_id, target_group_id)
            next_pos += 1

        conn.execute(
            "INSERT OR IGNORE INTO music_tag_assignments (tag_id, video_id, created_at) SELECT ?,video_id,? FROM music_tag_assignments WHERE tag_id=?",
            (target_id, now, source_id),
        )
        conn.execute(
            """
            INSERT INTO music_tag_playlist_links (playlist_id, tag_id, created_at, updated_at)
            SELECT playlist_id, ?, created_at, ?
            FROM music_tag_playlist_links WHERE tag_id=?
            ON CONFLICT(playlist_id) DO UPDATE SET tag_id=excluded.tag_id, updated_at=excluded.updated_at
            """,
            (target_id, now, source_id),
        )
        _sync_tag_playlist_assignments(conn, target_id)
        conn.execute("DELETE FROM music_tags WHERE id=?", (source_id,))

        if source["parent_id"] is None:
            _renumber_parent(conn, None, source_group_id)
        else:
            _renumber_parent(conn, int(source["parent_id"]))
        _renumber_parent(conn, target_id)
        conn.commit()
    finally:
        conn.close()


def delete_music_tag(tag_id: int):
    conn = get_db()
    try:
        row = conn.execute("SELECT id, parent_id FROM music_tags WHERE id=?", (tag_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Music tag not found")
        parent_id = int(row["parent_id"]) if row["parent_id"] is not None else None
        conn.execute("UPDATE music_tags SET parent_id=? WHERE parent_id=?", (parent_id, tag_id))
        conn.execute("DELETE FROM music_tag_assignments WHERE tag_id=?", (tag_id,))
        conn.execute("DELETE FROM music_tags WHERE id=?", (tag_id,))
        conn.commit()
    finally:
        conn.close()
