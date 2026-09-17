from datetime import datetime

import home_dashboard.features.trash as trash_module


def _mock_config() -> dict:
    return {
        "trash": {
            "display_switch_time": "08:00",
            "types": [
                {
                    "name": "燃えるゴミ",
                    "icon": "🔥",
                    "schedule": [{"type": "weekly", "weekdays": ["mon"]}],
                }
            ],
            "exclusions": [],
        }
    }


def test_weekly_schedule_before_switch_time(monkeypatch) -> None:
    monkeypatch.setattr(trash_module, "_load_config", lambda: _mock_config())

    context = trash_module.load_feature_context(datetime(2026, 9, 21, 7, 59))

    assert context["display"]["target_date"] == "2026-09-21"
    assert context["display"]["collections"] == [{"icon": "🔥", "name": "燃えるゴミ"}]


def test_switch_time_uses_tomorrow_after_cutoff(monkeypatch) -> None:
    monkeypatch.setattr(trash_module, "_load_config", lambda: _mock_config())

    context = trash_module.load_feature_context(datetime(2026, 9, 21, 8, 0))

    assert context["display"]["target_date"] == "2026-09-22"
    assert context["display"]["is_tomorrow"] is True
    assert context["display"]["collections"] == []
