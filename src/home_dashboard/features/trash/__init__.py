"""Trash collection calendar feature."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import re
import tomllib
from typing import Any

FEATURE_ID = "trash"
CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "trash.toml"

WEEKDAY_NAMES_JA = (
    "月曜日",
    "火曜日",
    "水曜日",
    "木曜日",
    "金曜日",
    "土曜日",
    "日曜日",
)
WEEKDAY_KEYS = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}
DATE_RE = re.compile(
    r"^(?:(?P<year>\d{4})[/-]?)?(?P<month>\d{1,2})[/-]?(?P<day>\d{1,2})$"
)
TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")


@dataclass(frozen=True)
class CalendarDate:
    year: int | None
    month: int
    day: int


def load_feature_context(now: datetime | None = None) -> dict[str, Any]:
    """Return the current display state and settings for the trash tile."""
    if now is None:
        now = datetime.now()

    config = _load_config()
    switch_time = _parse_time(config.get("trash", {}).get("display_switch_time", "08:00"))
    target_date = now.date() if now.time() < switch_time else now.date() + timedelta(days=1)
    types = _load_trash_types(config)
    exclusions = _load_exclusions(config)

    return {
        "display": {
            "target_date": target_date.isoformat(),
            "is_tomorrow": target_date == now.date() + timedelta(days=1),
            "weekday": WEEKDAY_NAMES_JA[target_date.weekday()],
            "collections": _collections_for_date(target_date, types, exclusions),
        },
        "calendar": {
            "types": [
                {
                    "name": item["name"],
                    "icon": item["icon"],
                    "schedule": item["schedule"],
                }
                for item in types
            ],
            "exclusions": [
                {
                    "start": _format_calendar_date(item["start"]),
                    "end": _format_calendar_date(item["end"]),
                }
                for item in exclusions
            ],
        },
        "settings": {
            "display_switch_time": f"{switch_time.hour:02d}:{switch_time.minute:02d}",
            "types": [
                {
                    "name": item["name"],
                    "icon": item["icon"],
                    "schedule_text": _schedule_text(item["schedule"]),
                }
                for item in types
            ],
            "exclusions": _visible_exclusions(now.date(), exclusions),
        },
    }


def _load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def _load_trash_types(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_types = config.get("trash", {}).get("types", [])
    if not isinstance(raw_types, list):
        raise ValueError("[trash].types must be an array")

    types: list[dict[str, Any]] = []
    for raw_type in raw_types:
        if not isinstance(raw_type, dict):
            raise ValueError("Each trash type must be a table")

        name = str(raw_type.get("name", "")).strip()
        icon = str(raw_type.get("icon", "")).strip()
        schedule = raw_type.get("schedule", [])
        if not name:
            raise ValueError("Trash type name must not be empty")
        if not isinstance(schedule, list):
            raise ValueError(f"schedule must be an array for {name}")

        normalized_schedule: list[dict[str, Any]] = []
        for rule in schedule:
            if not isinstance(rule, dict):
                raise ValueError(f"Each schedule rule must be a table for {name}")
            normalized_schedule.append(_normalize_schedule_rule(rule, name))

        types.append({"name": name, "icon": icon, "schedule": normalized_schedule})

    return types


def _normalize_schedule_rule(rule: dict[str, Any], trash_name: str) -> dict[str, Any]:
    rule_type = str(rule.get("type", "")).strip()
    if rule_type == "weekly":
        weekdays = rule.get("weekdays", [])
        if not isinstance(weekdays, list) or not weekdays:
            raise ValueError(f"weekly rule requires weekdays for {trash_name}")
        normalized = []
        for weekday in weekdays:
            key = str(weekday).lower()
            if key not in WEEKDAY_KEYS:
                raise ValueError(f"Unknown weekday '{weekday}' for {trash_name}")
            normalized.append(key)
        return {"type": rule_type, "weekdays": normalized}

    if rule_type == "nth_weekday":
        weekday = str(rule.get("weekday", "")).lower()
        nth = rule.get("nth", [])
        if weekday not in WEEKDAY_KEYS:
            raise ValueError(f"Unknown weekday '{weekday}' for {trash_name}")
        if not isinstance(nth, list) or not nth:
            raise ValueError(f"nth_weekday rule requires nth for {trash_name}")
        normalized_nth = []
        for value in nth:
            number = int(value)
            if not 1 <= number <= 5:
                raise ValueError(f"nth must be between 1 and 5 for {trash_name}")
            normalized_nth.append(number)
        return {"type": rule_type, "weekday": weekday, "nth": normalized_nth}

    raise ValueError(f"Unknown schedule type '{rule_type}' for {trash_name}")


def _load_exclusions(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_exclusions = config.get("trash", {}).get("exclusions", [])
    if not isinstance(raw_exclusions, list):
        raise ValueError("[trash].exclusions must be an array")

    exclusions: list[dict[str, Any]] = []
    for raw_exclusion in raw_exclusions:
        if not isinstance(raw_exclusion, dict):
            raise ValueError("Each exclusion must be a table")

        start = _parse_calendar_date(str(raw_exclusion.get("start", "")))
        end = _parse_calendar_date(str(raw_exclusion.get("end", raw_exclusion.get("start", ""))))
        if (start.year is None) != (end.year is None):
            raise ValueError("Exclusion start/end must both include a year or both omit it")
        if start.year is not None:
            start_date = date(start.year, start.month, start.day)
            end_date = date(end.year, end.month, end.day)
            if start_date > end_date:
                raise ValueError("A fixed-year exclusion cannot end before it starts")
        exclusions.append({"start": start, "end": end})

    return exclusions


def _parse_calendar_date(value: str) -> CalendarDate:
    match = DATE_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Invalid exclusion date: {value}")

    year_text = match.group("year")
    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        date(2000 if year_text is None else int(year_text), month, day)
    except ValueError as exc:
        raise ValueError(f"Invalid exclusion date: {value}") from exc
    return CalendarDate(None if year_text is None else int(year_text), month, day)


def _parse_time(value: str) -> time:
    match = TIME_RE.fullmatch(str(value).strip())
    if match is None:
        raise ValueError(f"Invalid display_switch_time: {value}")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23 or minute > 59:
        raise ValueError(f"Invalid display_switch_time: {value}")
    return time(hour, minute)


def _collections_for_date(
    target_date: date,
    types: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if any(_is_excluded(target_date, exclusion) for exclusion in exclusions):
        return []

    collections: list[dict[str, str]] = []
    for trash_type in types:
        if any(_matches_schedule(target_date, rule) for rule in trash_type["schedule"]):
            collections.append({"icon": trash_type["icon"], "name": trash_type["name"]})
    return collections


def _matches_schedule(target_date: date, rule: dict[str, Any]) -> bool:
    if rule["type"] == "weekly":
        return target_date.weekday() in {WEEKDAY_KEYS[key] for key in rule["weekdays"]}

    weekday = WEEKDAY_KEYS[rule["weekday"]]
    if target_date.weekday() != weekday:
        return False

    # 「第N○曜日」は、その月にとってのN回目の○曜日です。
    occurrence = (target_date.day - 1) // 7 + 1
    return occurrence in set(rule["nth"])


def _is_excluded(target_date: date, exclusion: dict[str, Any]) -> bool:
    start = exclusion["start"]
    end = exclusion["end"]

    if start.year is not None:
        return date(start.year, start.month, start.day) <= target_date <= date(
            end.year, end.month, end.day
        )

    for base_year in (target_date.year - 1, target_date.year, target_date.year + 1):
        start_date = date(base_year, start.month, start.day)
        end_year = base_year + 1 if (start.month, start.day) > (end.month, end.day) else base_year
        end_date = date(end_year, end.month, end.day)
        if start_date <= target_date <= end_date:
            return True
    return False


def _visible_exclusions(today: date, exclusions: list[dict[str, Any]]) -> list[str]:
    horizon = _add_one_month(today)
    visible: list[str] = []

    for exclusion in exclusions:
        start = exclusion["start"]
        end = exclusion["end"]
        if start.year is not None:
            start_date = date(start.year, start.month, start.day)
            end_date = date(end.year, end.month, end.day)
            if end_date < today or start_date > horizon:
                continue
            visible.append(_format_fixed_exclusion(start_date, end_date))
            continue

        upcoming = _next_recurring_interval(today, start, end)
        if upcoming is None:
            continue
        start_date, _ = upcoming
        if start_date > horizon:
            continue
        visible.append(_format_recurring_exclusion(start, end))

    return visible


def _next_recurring_interval(
    today: date,
    start: CalendarDate,
    end: CalendarDate,
) -> tuple[date, date] | None:
    for base_year in (today.year - 1, today.year, today.year + 1):
        start_date = date(base_year, start.month, start.day)
        end_year = base_year + 1 if (start.month, start.day) > (end.month, end.day) else base_year
        end_date = date(end_year, end.month, end.day)
        if end_date >= today:
            return start_date, end_date
    return None


def _add_one_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    following_year = year + (1 if month == 12 else 0)
    following_month = 1 if month == 12 else month + 1
    first_of_following_month = date(following_year, following_month, 1)
    last_day = first_of_following_month - timedelta(days=1)
    return last_day if value.day > last_day.day else date(year, month, value.day)


def _format_calendar_date(value: CalendarDate) -> str:
    if value.year is None:
        return f"{value.month}/{value.day}"
    return f"{value.year}/{value.month}/{value.day}"


def _format_fixed_exclusion(start: date, end: date) -> str:
    if start == end:
        return f"{start.year}/{start.month}/{start.day}"
    return f"{start.year}/{start.month}/{start.day}～{end.year}/{end.month}/{end.day}"


def _format_recurring_exclusion(start: CalendarDate, end: CalendarDate) -> str:
    if (start.month, start.day) == (end.month, end.day):
        return f"毎年 {start.month}/{start.day}"
    return f"毎年 {start.month}/{start.day}～{end.month}/{end.day}"


def _schedule_text(schedule: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for rule in schedule:
        if rule["type"] == "weekly":
            weekdays = "・".join(_weekday_label(key) for key in rule["weekdays"])
            parts.append(f"毎週 {weekdays}曜日")
        else:
            nth = "・".join(str(value) for value in rule["nth"])
            parts.append(f"第{nth}{_weekday_label(rule['weekday'])}曜日")
    return "、".join(parts)


def _weekday_label(key: str) -> str:
    return {
        "mon": "月",
        "tue": "火",
        "wed": "水",
        "thu": "木",
        "fri": "金",
        "sat": "土",
        "sun": "日",
    }[key]
