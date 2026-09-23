from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from home_dashboard.features.habits.config import (
    HabitDefinition,
    HabitSettings,
    habit_day_for_datetime,
    parse_settings,
)
from home_dashboard.features.habits.repository import HabitRecord, HabitRecordRepository
from home_dashboard.features.habits.service import HabitService
import home_dashboard.features.habits as habits_module

JST = timezone(timedelta(hours=9))


class MemoryRepository:
    def __init__(self, records: list[HabitRecord] | None = None) -> None:
        self.records = list(records or [])
        self.next_id = max((record.id for record in self.records), default=0) + 1

    def list_records(self, habit_id: str) -> list[HabitRecord]:
        return sorted(
            [record for record in self.records if record.habit_id == habit_id],
            key=lambda record: (record.done_at, record.id),
        )

    def list_records_for_habit_day(
        self, habit_id: str, day: date, boundary: time
    ) -> list[HabitRecord]:
        start = datetime.combine(day, boundary, tzinfo=JST)
        end = start + timedelta(days=1)
        return [
            record
            for record in self.list_records(habit_id)
            if start <= record.done_at < end
        ]

    def insert_for_habit_day(
        self, habit_id: str, day: date, boundary: time, occurrence: int
    ) -> HabitRecord:
        existing = self.list_records_for_habit_day(habit_id, day, boundary)
        while len(existing) < occurrence:
            done_at = datetime.combine(day, boundary, tzinfo=JST) + timedelta(
                hours=12, minutes=len(existing)
            )
            record = HabitRecord(self.next_id, habit_id, done_at)
            self.next_id += 1
            self.records.append(record)
            existing = self.list_records_for_habit_day(habit_id, day, boundary)
        return existing[occurrence - 1]

    def delete_for_habit_day_occurrence(
        self, habit_id: str, day: date, boundary: time, occurrence: int
    ) -> bool:
        existing = self.list_records_for_habit_day(habit_id, day, boundary)
        if len(existing) < occurrence:
            return False
        record_id = existing[occurrence - 1].id
        self.records = [record for record in self.records if record.id != record_id]
        return True


def _settings(
    *habits: HabitDefinition,
    display_emoji_count: int = 12,
    log_margin: float = 12,
    record_margin: float = 12,
) -> HabitSettings:
    return HabitSettings(
        display_emoji_count, time(6, 0), log_margin, record_margin, tuple(habits)
    )


def _habit(
    habit_id: str = "workout",
    name: str = "筋トレ",
    period: str = "week",
    target_count: int = 3,
    reset_date: date | None = None,
) -> HabitDefinition:
    return HabitDefinition(
        id=habit_id,
        name=name,
        emoji="💪",
        period=period,
        target_count=target_count,
        tree_milestone_streak=30,
        best_streak_reset_date=reset_date,
    )


def _record(record_id: int, habit_id: str, day: date) -> HabitRecord:
    return HabitRecord(
        record_id,
        habit_id,
        datetime.combine(day, time(12, 0), tzinfo=JST),
    )


def test_parse_settings_supports_zero_to_four_and_rejects_five() -> None:
    config = {"habit_tracker": {"display_emoji_count": 12, "day_boundary": "06:00"}}
    settings = parse_settings(config)
    assert settings.habits == ()

    habits = [
        {"id": f"h{i}", "name": f"習慣{i}", "emoji": "🌱", "period": "day", "target_count": 1}
        for i in range(4)
    ]
    settings = parse_settings({**config, "habits": habits})
    assert len(settings.habits) == 4

    habits.append({"id": "h4", "name": "習慣4", "emoji": "🌱", "period": "day", "target_count": 1})
    try:
        parse_settings({**config, "habits": habits})
    except ValueError as exc:
        assert "At most 4" in str(exc)
    else:
        raise AssertionError("five habits must be rejected")


def test_habit_day_boundary_uses_japan_time() -> None:
    assert habit_day_for_datetime(
        datetime(2026, 9, 21, 5, 59, tzinfo=JST), time(6, 0)
    ) == date(2026, 9, 20)
    assert habit_day_for_datetime(
        datetime(2026, 9, 21, 6, 0, tzinfo=JST), time(6, 0)
    ) == date(2026, 9, 21)


def test_weekly_current_progress_and_history_use_exact_emoji_count() -> None:
    habit = _habit(target_count=3)
    records = [
        _record(1, habit.id, date(2026, 9, 15)),
        _record(2, habit.id, date(2026, 9, 15)),
        _record(3, habit.id, date(2026, 9, 15)),  # previous week complete
        _record(4, habit.id, date(2026, 9, 8)),  # two weeks ago incomplete
        _record(5, habit.id, date(2026, 9, 21)),
        _record(6, habit.id, date(2026, 9, 21)),  # current week 2/3
    ]
    service = HabitService(
        _settings(habit, display_emoji_count=5),
        MemoryRepository(records),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )

    state = service.build_state()
    item = state["habits"][0]
    assert item["history"] == [
        {"kind": "past", "achieved": False},
        {"kind": "past", "achieved": True},
        {"kind": "current", "count": 2, "target_count": 3, "completed": False},
    ]
    assert item["current_streak"] == 1


def test_current_period_becomes_tree_as_soon_as_target_is_reached() -> None:
    habit = _habit(target_count=2)
    records = [_record(1, habit.id, date(2026, 9, 21)), _record(2, habit.id, date(2026, 9, 21))]
    service = HabitService(
        _settings(habit, display_emoji_count=4),
        MemoryRepository(records),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )
    item = service.build_state()["habits"][0]
    assert item["history"] == [
        {"kind": "past", "achieved": False},
        {"kind": "past", "achieved": False},
        {"kind": "past", "achieved": False},
        {"kind": "current", "count": 2, "target_count": 2, "completed": True},
    ]


def test_best_streak_ignores_records_on_or_before_reset_date() -> None:
    habit = _habit(target_count=1, reset_date=date(2026, 9, 13))
    records = [
        _record(1, habit.id, date(2026, 9, 7)),
        _record(2, habit.id, date(2026, 9, 14)),
        _record(3, habit.id, date(2026, 9, 21)),
    ]
    service = HabitService(
        _settings(habit, display_emoji_count=3),
        MemoryRepository(records),
        now=datetime(2026, 9, 22, 12, 0, tzinfo=JST),
    )
    item = service.build_state()["habits"][0]
    assert item["best_streak"] == 2


def test_record_summary_uses_requested_relative_words() -> None:
    week = _habit(period="week", target_count=2)
    week_service = HabitService(
        _settings(week),
        MemoryRepository([_record(1, week.id, date(2026, 9, 15))]),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )
    assert week_service.build_state(date(2026, 9, 20))["record"]["habits"][0]["progress_text"] == \
        "先週 1/2　7日目 0"

    month = _habit(habit_id="reading", period="month", target_count=2)
    month_service = HabitService(
        _settings(month),
        MemoryRepository([_record(1, month.id, date(2026, 8, 10))]),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )
    assert month_service.build_state(date(2026, 8, 20))["record"]["habits"][0]["progress_text"] == \
        "先月 1/2　20日目 0"

    day = _habit(habit_id="english", period="day", target_count=1)
    day_service = HabitService(
        _settings(day),
        MemoryRepository([_record(1, day.id, date(2026, 9, 20))]),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )
    assert (
        day_service.build_state(date(2026, 9, 20))["record"]["habits"][0]["progress_text"]
        == "昨日 1/1"
    )


def test_multiple_target_daily_progress_is_hole_and_seed_until_tree() -> None:
    habit = _habit(period="day", target_count=2)
    repository = MemoryRepository([_record(1, habit.id, date(2026, 9, 21))])
    service = HabitService(
        _settings(habit, display_emoji_count=2),
        repository,
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )
    item = service.build_state()["habits"][0]
    assert item["history"] == [
        {"kind": "current", "count": 1, "target_count": 2, "completed": False}
    ]

    repository.records.append(_record(2, habit.id, date(2026, 9, 21)))
    item = service.build_state()["habits"][0]
    assert item["history"] == [
        {"kind": "past", "achieved": False},
        {"kind": "current", "count": 2, "target_count": 2, "completed": True},
    ]


def test_state_can_use_an_arbitrary_past_habit_day() -> None:
    habit = _habit(target_count=1)
    service = HabitService(
        _settings(habit),
        MemoryRepository([_record(1, habit.id, date(2026, 8, 1))]),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )
    state = service.build_state(date(2026, 8, 1))
    assert state["selected_habit_day"] == "2026-08-01"
    assert state["record"]["habits"][0]["day_count"] == 1


def test_api_put_and_delete_are_state_explicit_and_use_temporary_db(tmp_path: Path) -> None:
    habit = _habit(habit_id="english", period="day", target_count=2)
    db_path = tmp_path / "test.db"
    repository = HabitRecordRepository(db_path)
    service = HabitService(
        _settings(habit, display_emoji_count=4),
        repository,
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )

    from home_dashboard.main import app

    app.dependency_overrides[habits_module.get_habit_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.get("/api/features/habits/state?selected_date=2026-08-01")
        assert response.status_code == 200
        assert response.json()["record"]["habits"][0]["day_count"] == 0

        response = client.put("/api/features/habits/english/records/2026-08-01/2")
        assert response.status_code == 200
        assert response.json()["ok"] is True

        response = client.get("/api/features/habits/state?selected_date=2026-08-01")
        data = response.json()
        record = data["record"]["habits"][0]
        assert record["day_count"] == 2
        assert record["progress_text"] == "この日 2/2"

        response = client.delete("/api/features/habits/english/records/2026-08-01/2")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

        response = client.get("/api/features/habits/state?selected_date=2026-08-01")
        assert response.json()["record"]["habits"][0]["day_count"] == 1
    finally:
        app.dependency_overrides.pop(habits_module.get_habit_service, None)


def test_zero_habits_is_a_valid_state() -> None:
    service = HabitService(
        _settings(display_emoji_count=12),
        MemoryRepository(),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )
    state = service.build_state()
    assert state["habits"] == []
    assert state["record"]["habits"] == []


def test_database_has_only_records_table_for_habits(tmp_path: Path) -> None:
    repository = HabitRecordRepository(tmp_path / "schema.db")
    repository.list_records("unused")
    import sqlite3

    with sqlite3.connect(tmp_path / "schema.db") as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info(habit_records)").fetchall()
        ]

    assert "habit_records" in tables
    assert "habits" not in tables
    assert "habit_rules" not in tables
    assert columns == ["id", "habit_id", "done_at"]


def test_record_state_marks_selected_day_occurrence_positions() -> None:
    habit = _habit(target_count=5)
    records = [
        _record(1, habit.id, date(2026, 9, 15)),
        _record(2, habit.id, date(2026, 9, 16)),
        _record(3, habit.id, date(2026, 9, 18)),
    ]
    service = HabitService(
        _settings(habit),
        MemoryRepository(records),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=JST),
    )

    state = service.build_state(date(2026, 9, 16))
    item = state["record"]["habits"][0]
    assert item["period_count"] == 3
    assert item["selected_occurrences"] == [2]

    state = service.build_state(date(2026, 9, 17))
    assert state["record"]["habits"][0]["selected_occurrences"] == []


def test_habit_settings_accept_horizontal_margins() -> None:
    settings = parse_settings({
        "habit_tracker": {
            "display_emoji_count": 12,
            "day_boundary": "06:00",
            "log_horizontal_margin_percent": 17,
            "record_horizontal_margin_percent": 23,
        }
    })
    assert settings.log_horizontal_margin_percent == 17
    assert settings.record_horizontal_margin_percent == 23


def test_habit_ui_keeps_record_layout_requirements() -> None:
    project_root = Path(__file__).resolve().parents[1]
    template = (project_root / "web" / "templates" / "features" / "habits.html").read_text(encoding="utf-8")
    script = (project_root / "web" / "static" / "features" / "habits" / "habits.js").read_text(encoding="utf-8")
    css = (project_root / "web" / "static" / "features" / "habits" / "habits.css").read_text(encoding="utf-8")

    assert 'data-action="today"' in template
    assert '今日に移動' in template
    assert "dateInput.value = current;" in script
    assert "i < count ? '🌱️' : '🕳️'" in script
    assert "Number(habit.target_count) > 1 || icons[j] === '🌳️'" in script
    assert "header.appendChild(habitIcon);" in script
    assert "iconColumn" not in script
    assert "item.appendChild(iconColumn);" not in script
    assert "feature-habits__adjust-group" in script
    assert "selected_occurrences" in script
    assert "if (overview.hidden) return;" in script
    assert "scheduleOverviewEmojiFit();" in script
    assert "feature-habits__progress-icon--active" in script
    assert "feature-habits__progress-icon--dim" in script
    assert "grid-template-rows: repeat(var(--habit-count, 1), minmax(0, 1fr));" in css
    assert "flex-direction: column;" in css
    assert "justify-content: center;" in css
    assert "justify-content: flex-start;" in css
    assert "feature-habits__record-item" in css
    assert "grid-template-columns: clamp(52px, 10vw, 84px)" not in css
    assert "grid-template-columns: clamp(44px, 10vw, 72px)" not in css
    assert "--habits-log-horizontal-margin" in css
    assert "--habits-record-horizontal-margin" in css
