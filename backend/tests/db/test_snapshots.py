"""Tests for portfolio snapshot policy."""

from __future__ import annotations

import sqlite3

from db import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    SNAPSHOT_DELTA_THRESHOLD,
    get_snapshots,
    record_snapshot,
)


def _count_snapshots(conn: sqlite3.Connection) -> int:
    (n,) = conn.execute(
        "SELECT COUNT(*) FROM portfolio_snapshots WHERE user_id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    return int(n)


class TestSnapshotPolicy:
    def test_seeded_snapshot_present(self, conn: sqlite3.Connection):
        assert _count_snapshots(conn) == 1
        snapshots = get_snapshots(conn)
        assert snapshots[0]["total_value"] == DEFAULT_CASH_BALANCE

    def test_heartbeat_below_threshold_skips(self, conn: sqlite3.Connection):
        # Seeded value is $10,000. A heartbeat at exactly the threshold or
        # below must NOT write.
        wrote = record_snapshot(
            conn, DEFAULT_CASH_BALANCE + SNAPSHOT_DELTA_THRESHOLD
        )
        assert wrote is False
        assert _count_snapshots(conn) == 1

        wrote = record_snapshot(
            conn, DEFAULT_CASH_BALANCE - SNAPSHOT_DELTA_THRESHOLD / 2
        )
        assert wrote is False
        assert _count_snapshots(conn) == 1

    def test_heartbeat_above_threshold_writes(self, conn: sqlite3.Connection):
        wrote = record_snapshot(
            conn, DEFAULT_CASH_BALANCE + SNAPSHOT_DELTA_THRESHOLD + 0.001
        )
        assert wrote is True
        assert _count_snapshots(conn) == 2

    def test_force_always_writes(self, conn: sqlite3.Connection):
        # Even at exactly the seeded value, force=True writes (used on trades).
        wrote = record_snapshot(conn, DEFAULT_CASH_BALANCE, force=True)
        assert wrote is True
        assert _count_snapshots(conn) == 2

    def test_get_snapshots_since(self, conn: sqlite3.Connection):
        # Insert a few extra snapshots with monotonic timestamps.
        record_snapshot(conn, 10100.0, force=True)
        record_snapshot(conn, 10200.0, force=True)
        all_snaps = get_snapshots(conn)
        assert len(all_snaps) == 3
        # Use the second snapshot's timestamp as the cutoff.
        since = all_snaps[1]["recorded_at"]
        bounded = get_snapshots(conn, since=since)
        assert len(bounded) == 2
        assert bounded[0]["recorded_at"] == since

    def test_get_snapshots_ordering(self, conn: sqlite3.Connection):
        record_snapshot(conn, 10500.0, force=True)
        record_snapshot(conn, 11000.0, force=True)
        snaps = get_snapshots(conn)
        # Oldest-first ordering.
        timestamps = [s["recorded_at"] for s in snaps]
        assert timestamps == sorted(timestamps)
