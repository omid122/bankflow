"""SQLite connection and schema setup.

SQLite (stdlib `sqlite3`, no ORM) was chosen deliberately: it satisfies the
persistence requirement (data survives process restarts, unlike an
in-memory dict) while keeping the delivered project dependency-free and
trivial to run inside Docker with no external services. See DESIGN.md /
ENGINEERING_DECISIONS.md for the full rationale.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS loans (
    loan_id         TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    amount          INTEGER NOT NULL,
    phone           TEXT NOT NULL,
    loan_type       TEXT NOT NULL,
    monthly_income  INTEGER NOT NULL,
    credit_score    INTEGER NOT NULL,
    has_guarantor   INTEGER NOT NULL,
    status          TEXT NOT NULL,
    current_stage   TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loan_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id     TEXT NOT NULL,
    stage       TEXT NOT NULL,
    result      TEXT NOT NULL,
    reason      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    UNIQUE(loan_id, stage),
    FOREIGN KEY(loan_id) REFERENCES loans(loan_id)
);
"""


class Database:
    """Thin wrapper around a single SQLite connection.

    A process-wide lock serializes writes so concurrent HTTP requests can
    never interleave partial transactions -- this is also what makes the
    "no duplicate processing" guarantee (FR-9) safe under concurrency.
    """

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn
