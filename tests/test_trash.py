from datetime import datetime

import pytest

from home_dashboard.features.trash import TrashConfigError, build_trash_calendar

CONFIG = {
    "cutover_time": "18:00",
    "types": {
        "burnable": {"label": "燃やすごみ", "icon": "🔥"},
        "recyclable": {"label": "資源ごみ", "icon": "♻"},
    },
    "rules": [
        {"weekday": "monday", "types": ["burnable"]},
        {"weekday": "wednesday", "occurrences": [1, 3], "types": ["recyclable"]},
    ],
    "excluded_dates": ["2026-09-21"],
}


def test_cutover_selects_today_or_tomorrow() -> None:
    before = build_trash_calendar(datetime(2026, 9, 14, 17, 59, 59), CONFIG)
    after = build_trash_calendar(datetime(2026, 9, 14, 18, 0), CONFIG)

    assert before["target_date"] == "2026-09-14"
    assert before["date_label"] == "9月14日"
    assert [item["id"] for item in before["items"]] == ["burnable"]
    assert after["target_date"] == "2026-09-15"
    assert after["date_label"] == "明日 9月15日"
    assert after["is_empty"] is True


def test_short_hour_cutover_time_is_supported() -> None:
    config = {**CONFIG, "cutover_time": "8:00"}

    calendar = build_trash_calendar(datetime(2026, 9, 14, 8, 0), config)

    assert calendar["target_date"] == "2026-09-15"


def test_nth_weekday_is_counted_by_weekday_occurrence() -> None:
    first = build_trash_calendar(datetime(2026, 9, 2, 12), CONFIG)
    second = build_trash_calendar(datetime(2026, 9, 9, 12), CONFIG)
    third = build_trash_calendar(datetime(2026, 9, 16, 12), CONFIG)

    assert [item["id"] for item in first["items"]] == ["recyclable"]
    assert second["is_empty"] is True
    assert [item["id"] for item in third["items"]] == ["recyclable"]


def test_excluded_date_has_no_collection() -> None:
    calendar = build_trash_calendar(datetime(2026, 9, 21, 12), CONFIG)

    assert calendar["is_empty"] is True


def test_multiple_trash_types_on_same_day_are_kept() -> None:
    config = {
        **CONFIG,
        "rules": [
            {"weekday": "monday", "types": ["burnable"]},
            {"weekday": "monday", "types": ["recyclable"]},
        ],
    }

    calendar = build_trash_calendar(datetime(2026, 9, 14, 12), config)

    assert [item["id"] for item in calendar["items"]] == ["burnable", "recyclable"]


def test_invalid_rule_type_is_rejected() -> None:
    config = {**CONFIG, "rules": [{"weekday": "monday", "types": ["unknown"]}]}

    with pytest.raises(TrashConfigError):
        build_trash_calendar(datetime(2026, 9, 14, 12), config)
