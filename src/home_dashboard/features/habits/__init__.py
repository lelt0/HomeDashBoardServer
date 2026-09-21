"""Habit tracker feature."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from home_dashboard.features.habits.config import load_settings
from home_dashboard.features.habits.repository import HabitRecordRepository
from home_dashboard.features.habits.service import HabitService

FEATURE_ID = "habits"
router = APIRouter(prefix="/api/features/habits", tags=[FEATURE_ID])


def load_feature_context() -> dict[str, Any]:
    settings = load_settings()
    return {
        "settings": {
            "display_emoji_count": settings.display_emoji_count,
            "day_boundary": settings.day_boundary.strftime("%H:%M"),
            "log_horizontal_margin_px": settings.log_horizontal_margin_px,
            "record_horizontal_margin_px": settings.record_horizontal_margin_px,
            "habits": [
                {
                    "id": habit.id,
                    "name": habit.name,
                    "emoji": habit.emoji,
                    "period": habit.period,
                    "target_count": habit.target_count,
                    "rule_text": f"{habit.target_count}回/{habit.period}",
                }
                for habit in settings.habits
            ],
        }
    }


def get_habit_service() -> HabitService:
    settings = load_settings()
    return HabitService(settings, HabitRecordRepository())


@router.get("/state")
def get_state(
    selected_date: date | None = None,
    service: HabitService = Depends(get_habit_service),
) -> dict[str, Any]:
    return service.build_state(selected_date)


@router.put("/{habit_id}/records/{habit_date}/{occurrence}")
def put_record(
    habit_id: str,
    habit_date: date,
    occurrence: int,
    service: HabitService = Depends(get_habit_service),
) -> dict[str, Any]:
    if occurrence < 1:
        raise HTTPException(status_code=400, detail="occurrence must be >= 1")
    try:
        record = service.add_record(habit_id, habit_date, occurrence)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Habit not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "record_id": record.id}


@router.delete("/{habit_id}/records/{habit_date}/{occurrence}")
def delete_record(
    habit_id: str,
    habit_date: date,
    occurrence: int,
    service: HabitService = Depends(get_habit_service),
) -> dict[str, Any]:
    if occurrence < 1:
        raise HTTPException(status_code=400, detail="occurrence must be >= 1")
    try:
        deleted = service.remove_record(habit_id, habit_date, occurrence)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Habit not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "deleted": deleted}
