import tomllib
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

WEEKDAYS = {
    "monday": (0, "月"),
    "tuesday": (1, "火"),
    "wednesday": (2, "水"),
    "thursday": (3, "木"),
    "friday": (4, "金"),
    "saturday": (5, "土"),
    "sunday": (6, "日"),
}
TRASH_CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "trash.toml"


class TrashConfigError(ValueError):
    """ゴミ収集設定が不正な場合に発生する例外。"""


def _parse_cutover_time(value: Any) -> time:
    if not isinstance(value, str):
        raise TrashConfigError("cutover_timeはH:MM形式で指定してください")
    parts = value.split(":")
    if len(parts) != 2:
        raise TrashConfigError("cutover_timeはH:MM形式で指定してください")
    try:
        hour, minute = (int(part) for part in parts)
        return time(hour=hour, minute=minute)
    except ValueError as exc:
        raise TrashConfigError("cutover_timeはH:MM形式で指定してください") from exc


def validate_trash_config(config: dict[str, Any]) -> dict[str, Any]:
    try:
        cutover_time = _parse_cutover_time(config["cutover_time"])
        types = config["types"]
        rules = config["rules"]
    except KeyError as exc:
        raise TrashConfigError("trash設定に必要な項目がありません") from exc

    if cutover_time.second or cutover_time.microsecond:
        raise TrashConfigError("cutover_timeはHH:MM形式で指定してください")
    if not isinstance(types, dict) or not types:
        raise TrashConfigError("trash.typesを1件以上指定してください")

    for type_id, definition in types.items():
        if not isinstance(type_id, str) or not isinstance(definition, dict):
            raise TrashConfigError("ゴミ種別の形式が不正です")
        if not definition.get("label") or not definition.get("icon"):
            raise TrashConfigError(f"ゴミ種別 {type_id} のlabelまたはiconがありません")

    if not isinstance(rules, list):
        raise TrashConfigError("trash.rulesは配列で指定してください")
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("weekday") not in WEEKDAYS:
            raise TrashConfigError("ruleのweekdayが不正です")
        rule_types = rule.get("types")
        if not isinstance(rule_types, list) or not rule_types:
            raise TrashConfigError("ruleのtypesを1件以上指定してください")
        if any(type_id not in types for type_id in rule_types):
            raise TrashConfigError("ruleに未定義のゴミ種別があります")
        occurrences = rule.get("occurrences")
        if occurrences is not None and (
            not isinstance(occurrences, list)
            or not occurrences
            or any(not isinstance(value, int) or value < 1 for value in occurrences)
        ):
            raise TrashConfigError("occurrencesは1以上の整数配列で指定してください")

    excluded_dates = config.get("excluded_dates", [])
    if not isinstance(excluded_dates, list):
        raise TrashConfigError("excluded_datesは日付文字列の配列で指定してください")
    for value in excluded_dates:
        try:
            date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise TrashConfigError(f"除外日が不正です: {value}") from exc

    return config


def load_trash_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        raw_config = tomllib.load(file)
    config = raw_config.get("trash", raw_config)
    return validate_trash_config(config)


def _occurrence_in_month(target_date: date) -> int:
    first_day = target_date.replace(day=1)
    offset = (target_date.weekday() - first_day.weekday()) % 7
    first_matching_day = first_day + timedelta(days=offset)
    return ((target_date - first_matching_day).days // 7) + 1


def _matches_rule(target_date: date, rule: dict[str, Any]) -> bool:
    weekday, _ = WEEKDAYS[rule["weekday"]]
    if target_date.weekday() != weekday:
        return False
    occurrences = rule.get("occurrences")
    return occurrences is None or _occurrence_in_month(target_date) in occurrences


def _next_refresh_seconds(now: datetime, cutover_time: time) -> int:
    if now.time() < cutover_time:
        refresh_at = datetime.combine(now.date(), cutover_time)
    else:
        refresh_at = datetime.combine(now.date() + timedelta(days=1), time.min)
    return max(1, int((refresh_at - now).total_seconds()))


def build_trash_calendar(now: datetime, config: dict[str, Any]) -> dict[str, Any]:
    config = validate_trash_config(config)
    cutover_time = _parse_cutover_time(config["cutover_time"])
    target_date = now.date()
    is_tomorrow = now.time() >= cutover_time
    if is_tomorrow:
        target_date += timedelta(days=1)

    weekday_index, weekday_label = WEEKDAYS[
        next(name for name, (index, _) in WEEKDAYS.items() if index == target_date.weekday())
    ]
    excluded_dates = set(config.get("excluded_dates", []))
    items: list[dict[str, str]] = []
    if target_date.isoformat() not in excluded_dates:
        for rule in config["rules"]:
            if _matches_rule(target_date, rule):
                for type_id in rule["types"]:
                    if type_id not in {item["id"] for item in items}:
                        definition = config["types"][type_id]
                        items.append(
                            {
                                "id": type_id,
                                "label": definition["label"],
                                "icon": definition["icon"],
                            }
                        )

    return {
        "target_date": target_date.isoformat(),
        "date_label": (
            "明日 " if is_tomorrow else ""
        ) + f"{target_date.month}月{target_date.day}日",
        "weekday_label": weekday_label,
        "weekday_index": weekday_index,
        "items": items,
        "is_empty": not items,
        "refresh_after_seconds": _next_refresh_seconds(now, cutover_time),
    }


def load_trash_calendar(now: datetime, path: Path) -> dict[str, Any]:
    return build_trash_calendar(now, load_trash_config(path))
