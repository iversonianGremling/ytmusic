"""ytmusic — music & music-video frontend backend.

Owns music-mode user state (music playlists, music history, album ratings,
artist follows, music tags). Calls recommenderr for all external data and
recommendations.
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

DB_PATH = os.environ.get("DB_PATH", "/opt/ytmusic/data/ytmusic.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9003"))
RECOMMENDERR_URL = os.environ.get("RECOMMENDERR_URL", "http://127.0.0.1:9001")
RECOMMENDERR_TOKEN = os.environ.get("RECOMMENDERR_TOKEN", "")
SCHEMA_VERSION = 1


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA_PATH.read_text())
        con.execute(
            "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, time.time()),
        )
        con.commit()
    finally:
        con.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ytmusic", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "ytmusic",
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "recommenderr_url": RECOMMENDERR_URL,
    }


from backend.routers import playlists, history, ratings, artists, tags, music_categories  # noqa: E402

app.include_router(playlists.router)
app.include_router(history.router)
app.include_router(ratings.router)
app.include_router(artists.router)
app.include_router(tags.router)
app.include_router(music_categories.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=LISTEN_HOST, port=LISTEN_PORT)
