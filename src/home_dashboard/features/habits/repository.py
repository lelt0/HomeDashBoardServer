from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import sqlite3

from home_dashboard.database import database_transaction

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class HabitRecord:
    id: int
    habit_id: str
    done_at: datetime


class HabitRecordRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path

    def list_records(self, habit_id: str) -> list[HabitRecord]:
        with database_transaction(self.db_path) as connection:
            rows = connection.execute(
                "SELECT id, habit_id, done_at FROM habit_records "
                "WHERE habit_id = ? ORDER BY done_at, id",
                (habit_id,),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def list_records_in_range(
        self,
        habit_id: str,
        start: datetime,
        end: datetime,
    ) -> list[HabitRecord]:
        with database_transaction(self.db_path) as connection:
            rows = connection.execute(
                "SELECT id, habit_id, done_at FROM habit_records "
                "WHERE habit_id = ? AND done_at >= ? AND done_at < ? "
                "ORDER BY done_at, id",
                (habit_id, _format_datetime(start), _format_datetime(end)),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def list_records_for_habit_day(
        self,
        habit_id: str,
        day: date,
        boundary: time,
    ) -> list[HabitRecord]:
        start = datetime.combine(day, boundary, tzinfo=JST)
        end = start + timedelta(days=1)
        return self.list_records_in_range(habit_id, start, end)

    def insert_for_habit_day(
        self,
        habit_id: str,
        day: date,
        boundary: time,
        occurrence: int,
    ) -> HabitRecord:
        if occurrence < 1:
            raise ValueError("occurrence must be >= 1")

        with database_transaction(self.db_path) as connection:
            start = datetime.combine(day, boundary, tzinfo=JST)
            end = start + timedelta(days=1)
            rows = connection.execute(
                "SELECT id, habit_id, done_at FROM habit_records "
                "WHERE habit_id = ? AND done_at >= ? AND done_at < ? "
                "ORDER BY done_at, id",
                (habit_id, _format_datetime(start), _format_datetime(end)),
            ).fetchall()

            current_count = len(rows)
            while current_count < occurrence:
                done_at = start + timedelta(hours=12, minutes=current_count)
                connection.execute(
                    "INSERT INTO habit_records (habit_id, done_at) VALUES (?, ?)",
                    (habit_id, _format_datetime(done_at)),
                )
                current_count += 1

            rows = connection.execute(
                "SELECT id, habit_id, done_at FROM habit_records "
                "WHERE habit_id = ? AND done_at >= ? AND done_at < ? "
                "ORDER BY done_at, id",
                (habit_id, _format_datetime(start), _format_datetime(end)),
            ).fetchall()
            return _row_to_record(rows[occurrence - 1])

    def delete_for_habit_day_occurrence(
        self,
        habit_id: str,
        day: date,
        boundary: time,
        occurrence: int,
    ) -> bool:
        if occurrence < 1:
            raise ValueError("occurrence must be >= 1")

        with database_transaction(self.db_path) as connection:
            start = datetime.combine(day, boundary, tzinfo=JST)
            end = start + timedelta(days=1)
            rows = connection.execute(
                "SELECT id FROM habit_records "
                "WHERE habit_id = ? AND done_at >= ? AND done_at < ? "
                "ORDER BY done_at, id",
                (habit_id, _format_datetime(start), _format_datetime(end)),
            ).fetchall()
            if len(rows) < occurrence:
                return False
            record_id = int(rows[occurrence - 1][0])
            connection.execute("DELETE FROM habit_records WHERE id = ?", (record_id,))
            return True


def _row_to_record(row: sqlite3.Row) -> HabitRecord:
    return HabitRecord(
        id=int(row[0]),
        habit_id=str(row[1]),
        done_at=datetime.fromisoformat(str(row[2])).replace(tzinfo=JST),
    )


def _format_datetime(value: datetime) -> str:
    local = value.astimezone(JST)
    return local.replace(tzinfo=None).isoformat(timespec="seconds")
