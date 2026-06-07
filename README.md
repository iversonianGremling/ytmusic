<div align="center">

# ytmusic

**The music frontend backend of [yt-platform](https://github.com/iversonianGremling/recommenderr) — owns your playlists, ratings, and listening sessions.**

A small FastAPI service that holds *your* music state (playlists, listening history, album & track ratings, artist follows, tags, continue-listening) and delegates enrichment, recommendations, radio, and lyrics to [`recommenderr`](https://github.com/iversonianGremling/recommenderr).

[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/python-3-3776ab)](https://www.python.org/)
[![Storage](https://img.shields.io/badge/storage-SQLite-003b57)](https://www.sqlite.org/)
[![Port](https://img.shields.io/badge/port-9003-blue)](#configuration)
[![Self-hosted](https://img.shields.io/badge/self--hosted-yes-success)](#deployment)

</div>

---

## What is this?

`ytmusic` is one of three services in **yt-platform**, a self-hosted YouTube & YouTube Music frontend with a transparent recommendation engine. It is the **music-mode backend**: it owns user state for listening and serves it to the React music SPA.

The platform splits responsibilities cleanly:

- **`ytmusic` owns *your* state** — music playlists, listening history, album/track ratings, artist follows, tags, and playback-session state (current track, skip history, thumbs).
- **[`recommenderr`](https://github.com/iversonianGremling/recommenderr) owns the *outside world*** — music enrichment (MusicBrainz, Last.fm, Deezer, Discogs, Bandcamp, iTunes, Spotify), recommendations, in-library radio, and lyrics.

Keeping the external integrations in `recommenderr` means flaky third-party APIs or rate limits can never take down the music player itself.

> For the big picture (architecture diagram, the recommendation pipeline, routing, and deployment of all three services), see the **[yt-platform / recommenderr README](https://github.com/iversonianGremling/recommenderr)**.

## Features

- **Music playlists** — create, reorder, and manage playlists.
- **Listening history** — track plays and continue-listening state.
- **Ratings** — album- and track-level ratings.
- **Artist follows** — follow artists and surface their releases.
- **Tags & music categories** — tag tracks and group them into categories; tags feed back into recommendations.
- **Radio & recommendations** — endless in-library radio and recommendations, computed by `recommenderr`.
- **Lyrics & enrichment** — fetched via `recommenderr` (with Cloudflare-solver fallback).

## API surface

A FastAPI app exposing routers for each concern:

| Router             | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `playlists`        | Music playlists                          |
| `history`          | Listening history / continue-listening   |
| `ratings`          | Album & track ratings                    |
| `artists`          | Artist follows                           |
| `tags`             | Music tags                               |
| `music_categories` | Category grouping for music              |

CORS is enabled (`allow_origins=["*"]`). `GET /health` reports service status, schema version, and the configured `recommenderr` URL.

## Repository layout

```
ytmusic/
├── backend/
│   ├── main.py            FastAPI app + lifespan (DB init)
│   ├── schema.sql         SQLite schema (WAL, foreign keys)
│   ├── routers/           playlists, history, ratings, artists,
│   │                      tags, music_categories
│   ├── services/          music_tags, …
│   ├── clients/           recommenderr client
│   ├── db/
│   └── tests/             unit + integration (pytest)
├── requirements.txt
├── pytest.ini
└── .env.example
```

## Configuration

Copy `.env.example` to `.env` and adjust. Key variables:

| Variable                      | Default                        | Purpose                               |
| ----------------------------- | ------------------------------ | ------------------------------------- |
| `LISTEN_HOST` / `LISTEN_PORT` | `0.0.0.0` / `9003`             | Bind address                          |
| `DB_PATH`                     | `/opt/ytmusic/data/ytmusic.db` | SQLite database path                  |
| `RECOMMENDERR_URL`            | `http://127.0.0.1:9001`        | Where to reach the recommender        |
| `RECOMMENDERR_TOKEN`          | —                              | Bearer token shared with recommenderr |
| `INVIDIOUS_URL`               | —                              | Invidious instance (passed through)   |

`.env` is gitignored — never commit secrets.

## Development

```bash
# from ytmusic/
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python -m backend.main      # serves on :9003
python -m pytest            # run tests
```

## Deployment

Runs as a `systemd` service inside a Proxmox LXC (CT134), behind the shared nginx site, alongside `recommenderr` (`:9001`) and `ytvideo` (`:9002`).

```bash
#   ytmusic.service  →  python -m backend.main   (cwd /opt/ytmusic, :9003)
systemctl restart ytmusic
systemctl status  ytmusic
```

nginx routes `/api/music/` to this service; the music SPA is served at `/music/`.

## License

Personal / self-hosted project. No public license granted — adapt for your own use.
