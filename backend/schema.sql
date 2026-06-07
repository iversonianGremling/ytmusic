-- ytmusic.db
-- Owns: music-mode user state (music playlists, music watch history, album ratings,
-- artist follows, music tags).
-- Cross-DB references: music_library lives in recommenderr (cache), categories live in
-- ytvideo. References from this DB to those are opaque IDs (no FK).

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL
);

-- ----- Music playlists (mirror of the video playlist shape, scoped to music mode) -----

CREATE TABLE IF NOT EXISTS music_playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    source_playlist_id TEXT,
    source_updated_at REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_music_playlists_source_id
    ON music_playlists(source_playlist_id) WHERE source_playlist_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS music_playlist_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL REFERENCES music_playlists(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    thumbnail TEXT,
    duration INTEGER,
    author TEXT,
    author_id TEXT,
    position INTEGER NOT NULL,
    added_at REAL NOT NULL,
    source_managed INTEGER NOT NULL DEFAULT 0,
    UNIQUE(playlist_id, video_id)
);
CREATE INDEX IF NOT EXISTS idx_mpt_playlist ON music_playlist_tracks(playlist_id, position);

CREATE TABLE IF NOT EXISTS music_playlist_progress (
    playlist_id TEXT PRIMARY KEY,
    title TEXT,
    thumbnail TEXT,
    author TEXT,
    author_id TEXT,
    current_video_id TEXT,
    current_video_title TEXT,
    current_video_thumbnail TEXT,
    current_video_position INTEGER NOT NULL,
    current_video_duration INTEGER,
    queue_index INTEGER NOT NULL DEFAULT 0,
    total_items INTEGER,
    last_updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_music_playlist_progress_updated
    ON music_playlist_progress(last_updated DESC);

-- ----- Watch progress + history (music rows only; ytvideo owns video rows) -----

CREATE TABLE IF NOT EXISTS watch_progress (
    video_id TEXT PRIMARY KEY,
    title TEXT,
    thumbnail TEXT,
    duration INTEGER,
    author TEXT,
    author_id TEXT,
    position INTEGER NOT NULL,
    last_updated REAL NOT NULL,
    media_type TEXT NOT NULL DEFAULT 'music'
);

CREATE TABLE IF NOT EXISTS watch_history (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    thumbnail TEXT,
    duration INTEGER,
    author TEXT,
    author_id TEXT,
    watched_at REAL NOT NULL,
    listen_count INTEGER NOT NULL DEFAULT 1,
    first_listened_at REAL
);
CREATE INDEX IF NOT EXISTS idx_history_watched ON watch_history(watched_at DESC);

-- ----- Album ratings -----

CREATE TABLE IF NOT EXISTS album_ratings (
    album_key TEXT PRIMARY KEY,
    album_title TEXT NOT NULL,
    album_artist TEXT,
    cover_art TEXT,
    source TEXT,
    playlist_id TEXT,
    playlist_title TEXT,
    rating INTEGER NOT NULL,
    rated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_album_ratings_rated_at
    ON album_ratings(rated_at DESC);

CREATE TABLE IF NOT EXISTS album_tracks (
    video_id TEXT PRIMARY KEY,
    album_key TEXT NOT NULL,
    album_title TEXT NOT NULL,
    album_artist TEXT,
    playlist_id TEXT,
    playlist_title TEXT,
    track_index INTEGER,
    added_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_album_tracks_album_key
    ON album_tracks(album_key);

-- ----- Artist follows (user choice; release events themselves are in recommenderr) -----

CREATE TABLE IF NOT EXISTS artist_follows (
    artist_key TEXT PRIMARY KEY,
    artist_name TEXT NOT NULL,
    image TEXT,
    source TEXT,
    spotify_artist_id TEXT,
    deezer_artist_id TEXT,
    itunes_artist_id TEXT,
    last_release_key TEXT,
    last_release_title TEXT,
    last_release_date TEXT,
    last_release_cover_art TEXT,
    last_release_source TEXT,
    last_checked_at REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artist_follows_name
    ON artist_follows(lower(artist_name));

-- ----- Music tags (user-defined hierarchical tag tree) -----

CREATE TABLE IF NOT EXISTS music_tag_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    system_key TEXT UNIQUE,
    position INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_music_tag_groups_name
    ON music_tag_groups(lower(name));

CREATE TABLE IF NOT EXISTS music_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER REFERENCES music_tags(id) ON DELETE SET NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    kind TEXT NOT NULL DEFAULT 'existing',
    group_id INTEGER REFERENCES music_tag_groups(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_music_tags_parent
    ON music_tags(parent_id, position);
CREATE INDEX IF NOT EXISTS idx_music_tags_kind_parent
    ON music_tags(kind, parent_id, position);
CREATE INDEX IF NOT EXISTS idx_music_tags_group_parent
    ON music_tags(group_id, parent_id, position);

-- Note: original schema FK'd video_id to music_library(video_id). Since music_library
-- now lives in recommenderr.db, the FK is dropped — video_id is a soft cross-DB reference.
CREATE TABLE IF NOT EXISTS music_tag_assignments (
    tag_id INTEGER NOT NULL REFERENCES music_tags(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (tag_id, video_id)
);
CREATE INDEX IF NOT EXISTS idx_music_tag_assignments_video
    ON music_tag_assignments(video_id);

CREATE TABLE IF NOT EXISTS music_tag_playlist_links (
    playlist_id INTEGER PRIMARY KEY,
    tag_id INTEGER NOT NULL REFERENCES music_tags(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_music_tag_playlist_links_tag
    ON music_tag_playlist_links(tag_id);

-- ----- Album wishlist (pending / want-to-listen) -----

CREATE TABLE IF NOT EXISTS album_wishlist (
    album_key   TEXT PRIMARY KEY,
    album_title TEXT NOT NULL,
    album_artist TEXT,
    cover_art   TEXT,
    source      TEXT,
    added_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_album_wishlist_added
    ON album_wishlist(added_at DESC);
