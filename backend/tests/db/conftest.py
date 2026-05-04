"""Shared fixtures for database tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from db import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Path to a fresh SQLite file inside a per-test temp directory."""
    return tmp_path / "finally.db"


@pytest.fixture
def conn(db_path: Path):
    """Initialized connection against a fresh on-disk SQLite file."""
    connection = init_db(db_path)
    try:
        yield connection
    finally:
        connection.close()
