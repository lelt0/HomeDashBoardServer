from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "home_dashboard.db"
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS habit_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id TEXT NOT NULL,
    done_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_habit_records_habit_done
    ON habit_records (habit_id, done_at);
"""


def connect_database(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a configured SQLite connection and initialize shared tables."""
    db_path = Path(path) if path is not None else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(SCHEMA_SQL)
    connection.commit()
    return connection


@contextmanager
def database_transaction(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with transaction semantics for one operation."""
    connection = connect_database(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
