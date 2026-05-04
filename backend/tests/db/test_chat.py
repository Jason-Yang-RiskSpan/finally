"""Tests for chat_messages helpers."""

from __future__ import annotations

import sqlite3

import pytest

from db import add_chat_message, get_recent_chat_messages


SAMPLE_ACTIONS = {
    "trades": [
        {
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 10,
            "price": 191.42,
            "status": "executed",
        },
        {
            "ticker": "TSLA",
            "side": "buy",
            "quantity": 5,
            "status": "rejected",
            "reason": "insufficient_cash",
        },
    ],
    "watchlist_changes": [
        {"ticker": "PYPL", "action": "add", "status": "executed"},
        {
            "ticker": "ZZZZZ",
            "action": "add",
            "status": "rejected",
            "reason": "unknown_ticker",
        },
    ],
}


class TestChatMessages:
    def test_user_message_no_actions(self, conn: sqlite3.Connection):
        mid = add_chat_message(conn, role="user", content="how am I doing?")
        assert mid > 0
        messages = get_recent_chat_messages(conn)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["actions"] is None

    def test_user_message_rejects_actions(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError):
            add_chat_message(conn, role="user", content="x", actions=SAMPLE_ACTIONS)

    def test_assistant_actions_round_trip(self, conn: sqlite3.Connection):
        add_chat_message(
            conn, role="assistant", content="Bought AAPL.", actions=SAMPLE_ACTIONS
        )
        messages = get_recent_chat_messages(conn)
        assert len(messages) == 1
        assert messages[0]["actions"] == SAMPLE_ACTIONS
        # Specifically verify nested rejected entries survive JSON round-trip.
        rejected = messages[0]["actions"]["trades"][1]
        assert rejected["status"] == "rejected"
        assert rejected["reason"] == "insufficient_cash"

    def test_invalid_role_rejected(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError):
            add_chat_message(conn, role="system", content="x")  # type: ignore[arg-type]

    def test_recent_messages_oldest_first(self, conn: sqlite3.Connection):
        for i in range(5):
            add_chat_message(conn, role="user", content=f"msg-{i}")
        messages = get_recent_chat_messages(conn, limit=5)
        assert [m["content"] for m in messages] == [
            "msg-0",
            "msg-1",
            "msg-2",
            "msg-3",
            "msg-4",
        ]

    def test_recent_messages_limit(self, conn: sqlite3.Connection):
        for i in range(25):
            add_chat_message(conn, role="user", content=f"msg-{i}")
        messages = get_recent_chat_messages(conn, limit=20)
        assert len(messages) == 20
        # Should be the LAST 20 messages, oldest-first.
        assert messages[0]["content"] == "msg-5"
        assert messages[-1]["content"] == "msg-24"

    def test_recent_messages_zero_limit(self, conn: sqlite3.Connection):
        add_chat_message(conn, role="user", content="x")
        assert get_recent_chat_messages(conn, limit=0) == []
