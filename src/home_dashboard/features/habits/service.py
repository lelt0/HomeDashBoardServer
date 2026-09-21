from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from home_dashboard.features.habits.config import (
    HabitDefinition,
    HabitSettings,
    habit_day_for_datetime,
)
from home_dashboard.features.habits.repository import HabitRecord, HabitRecordRepository

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Period:
    start: date


class HabitService:
    def __init__(
        self,
        settings: HabitSettings,
        repository: HabitRecordRepository,
        now: datetime | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.now = now.astimezone(JST) if now is not None else datetime.now(JST)
        self.current_habit_day = habit_day_for_datetime(self.now, settings.day_boundary)

    def build_state(self, selected_habit_day: date | None = None) -> dict[str, Any]:
        selected = selected_habit_day or self.current_habit_day
        if selected > self.current_habit_day:
            selected = self.current_habit_day

        habits = [self._build_habit_state(habit) for habit in self.settings.habits]
        record_habits = [
            self._build_record_state(habit, selected)
            for habit in self.settings.habits
        ]
        return {
            "current_habit_day": self.current_habit_day.isoformat(),
            "selected_habit_day": selected.isoformat(),
            "habits": habits,
            "record": {"habits": record_habits},
        }

    def add_record(self, habit_id: str, selected_habit_day: date, occurrence: int) -> HabitRecord:
        habit = self._habit(habit_id)
        self._validate_selected_day(selected_habit_day)
        return self.repository.insert_for_habit_day(
            habit.id,
            selected_habit_day,
            self.settings.day_boundary,
            occurrence,
        )

    def remove_record(self, habit_id: str, selected_habit_day: date, occurrence: int) -> bool:
        habit = self._habit(habit_id)
        self._validate_selected_day(selected_habit_day)
        return self.repository.delete_for_habit_day_occurrence(
            habit.id,
            selected_habit_day,
            self.settings.day_boundary,
            occurrence,
        )

    def _build_habit_state(self, habit: HabitDefinition) -> dict[str, Any]:
        records = self.repository.list_records(habit.id)
        counts = self._period_counts(habit, records)
        current_period = self._period_for_day(habit, self.current_habit_day)
        current_count = counts.get(current_period.start, 0)
        history = self._history_units(habit, counts, current_period, current_count)
        current_streak = self._current_tree_streak(habit, counts, current_period, current_count)
        reset_counts = self._period_counts(habit, records, apply_reset=True)
        best_streak = self._best_tree_streak(habit, reset_counts, current_period)
        return {
            "id": habit.id,
            "name": habit.name,
            "emoji": habit.emoji,
            "period": habit.period,
            "target_count": habit.target_count,
            "rule_text": f"{habit.target_count}回/{habit.period}",
            "history": history,
            "current_streak": current_streak,
            "best_streak": best_streak,
            "tree_milestone_streak": habit.tree_milestone_streak,
        }

    def _build_record_state(
        self,
        habit: HabitDefinition,
        selected_habit_day: date,
    ) -> dict[str, Any]:
        records = self.repository.list_records(habit.id)
        selected_records = self.repository.list_records_for_habit_day(
            habit.id,
            selected_habit_day,
            self.settings.day_boundary,
        )
        counts = self._period_counts(habit, records)
        selected_period = self._period_for_day(habit, selected_habit_day)
        period_count = counts.get(selected_period.start, 0)
        period_records = [
            record
            for record in records
            if self._period_for_day(
                habit, habit_day_for_datetime(record.done_at, self.settings.day_boundary)
            ).start == selected_period.start
        ]
        selected_occurrences = [
            index
            for index, record in enumerate(period_records, start=1)
            if habit_day_for_datetime(record.done_at, self.settings.day_boundary) == selected_habit_day
        ]
        current_period = self._period_for_day(habit, self.current_habit_day)
        period_distance = self._period_distance(habit, selected_period, current_period)
        day_distance = (self.current_habit_day - selected_habit_day).days
        period_label = self._period_relative_label(habit, period_distance)

        if habit.period == "day":
            if habit.target_count == 1:
                progress_text = f"{self._day_relative_label(day_distance)} {period_count}/1"
            else:
                progress_text = f"この日 {period_count}/{habit.target_count}"
        else:
            progress_text = (
                f"{period_label} {period_count}/{habit.target_count} "
                f"この日 {len(selected_records)}"
            )

        return {
            "id": habit.id,
            "name": habit.name,
            "emoji": habit.emoji,
            "period": habit.period,
            "target_count": habit.target_count,
            "rule_text": f"{habit.target_count}回/{habit.period}",
            "selected_day": selected_habit_day.isoformat(),
            "period_start": selected_period.start.isoformat(),
            "period_count": period_count,
            "day_count": len(selected_records),
            "selected_occurrences": selected_occurrences,
            "progress": {
                "count": period_count,
                "target_count": habit.target_count,
                "completed": period_count >= habit.target_count,
            },
            "progress_text": progress_text,
        }

    def _history_units(
        self,
        habit: HabitDefinition,
        counts: dict[date, int],
        current_period: Period,
        current_count: int,
    ) -> list[dict[str, Any]]:
        emoji_count = self.settings.display_emoji_count
        current_unit = {
            "kind": "current",
            "count": min(current_count, habit.target_count),
            "target_count": habit.target_count,
            "completed": current_count >= habit.target_count,
        }
        blocks_newest_first: list[list[dict[str, Any]]] = [[current_unit]]
        current_icon_count = 1 if current_count >= habit.target_count else habit.target_count
        icon_total = current_icon_count
        period = current_period

        while icon_total < emoji_count:
            period = self._previous_period(habit, period)
            count = counts.get(period.start, 0)
            blocks_newest_first.append(
                [{
                    "kind": "past",
                    "achieved": count >= habit.target_count,
                }]
            )
            icon_total += 1

        units: list[dict[str, Any]] = []
        for block in reversed(blocks_newest_first):
            units.extend(block)
        return units[-emoji_count:]

    def _period_counts(
        self,
        habit: HabitDefinition,
        records: list[HabitRecord],
        apply_reset: bool = False,
    ) -> dict[date, int]:
        counts: Counter[date] = Counter()
        for record in records:
            habit_day = habit_day_for_datetime(record.done_at, self.settings.day_boundary)
            if apply_reset and habit.best_streak_reset_date is not None:
                if habit_day <= habit.best_streak_reset_date:
                    continue
            counts[self._period_for_day(habit, habit_day).start] += 1
        return dict(counts)

    def _current_tree_streak(
        self,
        habit: HabitDefinition,
        counts: dict[date, int],
        current_period: Period,
        current_count: int,
    ) -> int:
        # While the current period is still open, an unfinished current period does not
        # destroy the visible streak. The streak is the consecutive run ending in the
        # most recently completed period, and includes the current period once it is done.
        period = (
            current_period
            if current_count >= habit.target_count
            else self._previous_period(habit, current_period)
        )
        streak = 0
        while counts.get(period.start, 0) >= habit.target_count:
            streak += 1
            period = self._previous_period(habit, period)
        return streak

    def _best_tree_streak(
        self,
        habit: HabitDefinition,
        counts: dict[date, int],
        current_period: Period,
    ) -> int:
        if not counts:
            return 0
        first = min(counts)
        period = Period(first)
        best = 0
        current = 0
        while period.start <= current_period.start:
            if counts.get(period.start, 0) >= habit.target_count:
                current += 1
                best = max(best, current)
            else:
                current = 0
            period = self._next_period(habit, period)
        return best

    def _validate_selected_day(self, selected_habit_day: date) -> None:
        if selected_habit_day > self.current_habit_day:
            raise ValueError("Future habit days cannot be recorded")

    def _habit(self, habit_id: str) -> HabitDefinition:
        for habit in self.settings.habits:
            if habit.id == habit_id:
                return habit
        raise KeyError(habit_id)

    @staticmethod
    def _period_for_day(habit: HabitDefinition, habit_day: date) -> Period:
        if habit.period == "day":
            return Period(habit_day)
        if habit.period == "week":
            return Period(habit_day - timedelta(days=habit_day.weekday()))
        return Period(habit_day.replace(day=1))

    @staticmethod
    def _period_distance(habit: HabitDefinition, selected: Period, current: Period) -> int:
        if habit.period == "day":
            return (current.start - selected.start).days
        if habit.period == "week":
            return (current.start - selected.start).days // 7
        return (current.start.year * 12 + current.start.month) - (
            selected.start.year * 12 + selected.start.month
        )

    @staticmethod
    def _period_relative_label(habit: HabitDefinition, distance: int) -> str:
        if habit.period == "week":
            if distance == 0:
                return "今週"
            if distance == 1:
                return "先週"
            if distance == 2:
                return "先々週"
            return f"{distance}週前"
        if distance == 0:
            return "今月"
        if distance == 1:
            return "先月"
        if distance == 2:
            return "先々月"
        return f"{distance}月前"

    @staticmethod
    def _day_relative_label(distance: int) -> str:
        if distance == 0:
            return "今日"
        if distance == 1:
            return "昨日"
        if distance == 2:
            return "一昨日"
        return f"{distance}日前"

    @staticmethod
    def _previous_period(habit: HabitDefinition, period: Period) -> Period:
        if habit.period == "day":
            return Period(period.start - timedelta(days=1))
        if habit.period == "week":
            return Period(period.start - timedelta(days=7))
        previous_month = period.start.replace(day=1) - timedelta(days=1)
        return Period(previous_month.replace(day=1))

    @staticmethod
    def _next_period(habit: HabitDefinition, period: Period) -> Period:
        if habit.period == "day":
            return Period(period.start + timedelta(days=1))
        if habit.period == "week":
            return Period(period.start + timedelta(days=7))
        if period.start.month == 12:
            return Period(date(period.start.year + 1, 1, 1))
        return Period(date(period.start.year, period.start.month + 1, 1))

    def _period_end(self, habit: HabitDefinition, period: Period) -> date:
        return self._next_period(habit, period).start - timedelta(days=1)
