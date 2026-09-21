from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import re
import tomllib
from typing import Any

FEATURE_ID = "habits"
CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "habits.toml"
JST = timezone(timedelta(hours=9))
TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")
VALID_PERIODS = {"day", "week", "month"}


@dataclass(frozen=True)
class HabitDefinition:
    id: str
    name: str
    emoji: str
    period: str
    target_count: int
    tree_milestone_streak: int | None
    best_streak_reset_date: date | None


@dataclass(frozen=True)
class HabitSettings:
    display_emoji_count: int
    day_boundary: time
    log_horizontal_margin_px: int
    record_horizontal_margin_px: int
    habits: tuple[HabitDefinition, ...]


def load_settings(config_path: Path | str | None = None) -> HabitSettings:
    path = Path(config_path) if config_path is not None else CONFIG_PATH
    with path.open("rb") as file:
        config = tomllib.load(file)
    return parse_settings(config)


def parse_settings(config: dict[str, Any]) -> HabitSettings:
    common = config.get("habit_tracker", {})
    if not isinstance(common, dict):
        raise ValueError("[habit_tracker] must be a table")

    display_emoji_count = int(common.get("display_emoji_count", 12))
    if display_emoji_count < 1:
        raise ValueError("habit_tracker.display_emoji_count must be >= 1")

    day_boundary = _parse_time(str(common.get("day_boundary", "06:00")))

    log_horizontal_margin_px = int(common.get("log_horizontal_margin_px", 12))
    record_horizontal_margin_px = int(common.get("record_horizontal_margin_px", 12))
    if log_horizontal_margin_px < 0:
        raise ValueError("habit_tracker.log_horizontal_margin_px must be >= 0")
    if record_horizontal_margin_px < 0:
        raise ValueError("habit_tracker.record_horizontal_margin_px must be >= 0")

    raw_habits = config.get("habits", [])
    if not isinstance(raw_habits, list):
        raise ValueError("[[habits]] must be an array of tables")
    if len(raw_habits) > 4:
        raise ValueError("At most 4 habits may be configured")

    definitions: list[HabitDefinition] = []
    ids: set[str] = set()
    for raw_habit in raw_habits:
        if not isinstance(raw_habit, dict):
            raise ValueError("Each habit must be a table")

        habit_id = str(raw_habit.get("id", "")).strip()
        name = str(raw_habit.get("name", "")).strip()
        emoji = str(raw_habit.get("emoji", "")).strip()
        period = str(raw_habit.get("period", "")).strip().lower()
        target_count = int(raw_habit.get("target_count", 0))
        milestone_raw = raw_habit.get("tree_milestone_streak")
        reset_raw = raw_habit.get("best_streak_reset_date")

        if not habit_id:
            raise ValueError("habit.id must not be empty")
        if habit_id in ids:
            raise ValueError(f"Duplicate habit id: {habit_id}")
        if not name:
            raise ValueError(f"habit.name must not be empty for {habit_id}")
        if not emoji:
            raise ValueError(f"habit.emoji must not be empty for {habit_id}")
        if period not in VALID_PERIODS:
            raise ValueError(f"Unknown habit period '{period}' for {habit_id}")
        if target_count < 1:
            raise ValueError(f"habit.target_count must be >= 1 for {habit_id}")

        milestone = None if milestone_raw is None else int(milestone_raw)
        if milestone is not None and milestone < 1:
            raise ValueError(f"habit.tree_milestone_streak must be >= 1 for {habit_id}")

        reset_date = None
        if reset_raw is not None and str(reset_raw).strip():
            try:
                reset_date = date.fromisoformat(str(reset_raw).strip())
            except ValueError as exc:
                raise ValueError(
                    f"habit.best_streak_reset_date must be YYYY-MM-DD for {habit_id}"
                ) from exc

        definitions.append(
            HabitDefinition(
                id=habit_id,
                name=name,
                emoji=emoji,
                period=period,
                target_count=target_count,
                tree_milestone_streak=milestone,
                best_streak_reset_date=reset_date,
            )
        )
        ids.add(habit_id)

    if definitions and display_emoji_count < max(item.target_count for item in definitions):
        raise ValueError(
            "habit_tracker.display_emoji_count must be at least the largest habit target_count"
        )

    return HabitSettings(
        display_emoji_count=display_emoji_count,
        day_boundary=day_boundary,
        log_horizontal_margin_px=log_horizontal_margin_px,
        record_horizontal_margin_px=record_horizontal_margin_px,
        habits=tuple(definitions),
    )


def _parse_time(value: str) -> time:
    match = TIME_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Invalid time: {value}")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"Invalid time: {value}")
    return time(hour, minute)


def habit_day_for_datetime(value: datetime, boundary: time) -> date:
    local = value.astimezone(JST)
    if local.time().replace(tzinfo=None) < boundary:
        return local.date() - timedelta(days=1)
    return local.date()


def habit_day_start(day: date, boundary: time) -> datetime:
    return datetime.combine(day, boundary, tzinfo=JST)
