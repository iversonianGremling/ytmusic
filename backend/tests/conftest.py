"""Shared fixtures for ytmusic tests."""
from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path

import pytest


SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"
RECOMMENDERR_URL = "http://recommenderr.test"


@pytest.fixture
def tmp_db(monkeypatch):
    path = f"/tmp/ytmusic_test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("DB_PATH", path)
    monkeypatch.setenv("RECOMMENDERR_URL", RECOMMENDERR_URL)
    monkeypatch.setenv("RECOMMENDERR_TOKEN", "test-token")
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA_PATH.read_text())
        con.commit()
    finally:
        con.close()
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def app(tmp_db):
    from backend.main import app as _app

    return _app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


