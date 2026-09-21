"""Shared SQLite database infrastructure for Home Dashboard."""

from home_dashboard.database.connection import (
    DEFAULT_DB_PATH,
    connect_database,
    database_transaction,
)

__all__ = ["DEFAULT_DB_PATH", "connect_database", "database_transaction"]
