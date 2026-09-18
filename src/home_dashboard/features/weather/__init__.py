"""Weather forecast feature."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import tomllib
from typing import Any, Callable
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException

FEATURE_ID = "weather"
CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "weather.toml"
API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE_NAME = "Asia/Tokyo"
JST = timezone(timedelta(hours=9))

WEEKDAY_NAMES_JA = ("月", "火", "水", "木", "金", "土", "日")

# WMO weather interpretation codes used by Open-Meteo.
WEATHER_ICONS = {
    0: "☀️",
    1: "🌤️",
    2: "⛅",
    3: "☁️",
    45: "🌫️",
    48: "🌫️",
    51: "🌦️",
    53: "🌦️",
    55: "🌧️",
    56: "🌧️",
    57: "🌧️",
    61: "🌧️",
    63: "🌧️",
    65: "🌧️",
    66: "🌧️",
    67: "🌧️",
    71: "🌨️",
    73: "🌨️",
    75: "🌨️",
    77: "🌨️",
    80: "🌦️",
    81: "🌦️",
    82: "🌧️",
    85: "🌨️",
    86: "🌨️",
    95: "⛈️",
    96: "⛈️",
    99: "⛈️",
}


def load_feature_context() -> dict[str, Any]:
    """Return weather feature settings for the dashboard template."""
    settings = _load_settings()
    return {"settings": settings}


def _load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)


def _load_settings() -> dict[str, Any]:
    config = _load_config()
    raw = config.get("weather", {})
    if not isinstance(raw, dict):
        raise ValueError("[weather] must be a table")

    region = str(raw.get("region", "")).strip()
    if not region:
        raise ValueError("weather.region must not be empty")

    latitude = float(raw.get("latitude"))
    longitude = float(raw.get("longitude"))
    if not -90 <= latitude <= 90:
        raise ValueError("weather.latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError("weather.longitude must be between -180 and 180")

    no_rain_threshold = float(raw.get("no_rain_max_mm_per_hour", 0.0))
    light_rain_threshold = float(raw.get("light_rain_max_mm_per_hour", 2.0))
    background = raw.get("background", {})
    if not isinstance(background, dict):
        raise ValueError("[weather.background] must be a table")

    background_colors = {
        "sunny": str(background.get("sunny", "#151515")),
        "cloudy": str(background.get("cloudy", "#151515")),
        "light_rain": str(background.get("light_rain", "#10191b")),
        "rain": str(background.get("rain", "#0f1820")),
    }

    if no_rain_threshold < 0:
        raise ValueError("weather.no_rain_max_mm_per_hour must be >= 0")
    if light_rain_threshold < no_rain_threshold:
        raise ValueError(
            "weather.light_rain_max_mm_per_hour must be >= "
            "weather.no_rain_max_mm_per_hour"
        )

    return {
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "no_rain_max_mm_per_hour": no_rain_threshold,
        "light_rain_max_mm_per_hour": light_rain_threshold,
        "background": background_colors,
    }


class WeatherCache:
    """In-process cache of the last successfully fetched weather forecast."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] | None = None
        self._fetched_at: datetime | None = None

    def get(self) -> tuple[dict[str, Any] | None, datetime | None]:
        with self._lock:
            return self._data, self._fetched_at

    def set(self, data: dict[str, Any], fetched_at: datetime) -> None:
        with self._lock:
            self._data = data
            self._fetched_at = fetched_at


CACHE = WeatherCache()
router = APIRouter(prefix="/api/features/weather", tags=[FEATURE_ID])


@router.get("")
def get_weather() -> dict[str, Any]:
    """Fetch the latest forecast and return the weather feature display state."""
    settings = _load_settings()
    try:
        payload = _fetch_forecast(settings)
        fetched_at = datetime.now(JST)
        data = _build_display_data(payload, settings, fetched_at)
    except Exception as exc:
        cached, cached_at = CACHE.get()
        if cached is not None and cached_at is not None:
            return {
                "ok": False,
                "data": cached,
                "fetched_at": cached_at.isoformat(),
                "error": "weather fetch failed; using cached forecast",
            }
        raise HTTPException(status_code=503, detail="Weather forecast is unavailable") from exc

    CACHE.set(data, fetched_at)
    return {"ok": True, "data": data, "fetched_at": fetched_at.isoformat()}


def _fetch_forecast(
    settings: dict[str, Any],
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "latitude": settings["latitude"],
            "longitude": settings["longitude"],
            "hourly": "precipitation,precipitation_probability,weather_code",
            "daily": "weather_code",
            "forecast_days": 7,
            "timezone": TIMEZONE_NAME,
        }
    )
    request = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"User-Agent": "HomeDashBoardServer/0.1"},
        method="GET",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_display_data(
    payload: dict[str, Any], settings: dict[str, Any], fetched_at: datetime
) -> dict[str, Any]:
    hourly = payload.get("hourly")
    daily = payload.get("daily")
    if not isinstance(hourly, dict) or not isinstance(daily, dict):
        raise ValueError("Open-Meteo response is missing hourly or daily data")

    hourly_times = hourly.get("time")
    precipitation = hourly.get("precipitation")
    precipitation_probability = hourly.get("precipitation_probability")
    hourly_weather_codes = hourly.get("weather_code")
    daily_times = daily.get("time")
    daily_weather_codes = daily.get("weather_code")

    if not isinstance(hourly_times, list) or not isinstance(precipitation, list):
        raise ValueError("Open-Meteo hourly data is invalid")
    if len(hourly_times) != len(precipitation):
        raise ValueError("Open-Meteo hourly arrays have different lengths")
    if (
        precipitation_probability is not None
        and len(precipitation_probability) != len(hourly_times)
    ):
        raise ValueError("Open-Meteo precipitation probability array is invalid")
    if (
        not isinstance(hourly_weather_codes, list)
        or len(hourly_weather_codes) != len(hourly_times)
    ):
        raise ValueError("Open-Meteo hourly weather code array is invalid")
    if not isinstance(daily_times, list) or not isinstance(daily_weather_codes, list):
        raise ValueError("Open-Meteo daily data is invalid")
    if len(daily_times) != len(daily_weather_codes):
        raise ValueError("Open-Meteo daily arrays have different lengths")

    now = fetched_at
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=6)
    values = _extract_six_hour_values(
        hourly_times,
        precipitation,
        precipitation_probability,
        hourly_weather_codes,
        start,
    )
    max_precipitation = max(item["precipitation"] for item in values)
    max_probability = _max_or_none(item["probability"] for item in values)
    icon = _rain_icon(values, settings)

    return {
        "region": settings["region"],
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": _period_label(start, end),
        },
        "current": {
            "icon": icon,
            "max_precipitation_mm_per_hour": max_precipitation,
            "max_precipitation_probability": max_probability,
        },
        "daily": _build_daily_forecast(daily_times, daily_weather_codes, fetched_at.date()),
    }


def _extract_six_hour_values(
    hourly_times: list[Any],
    precipitation: list[Any],
    precipitation_probability: list[Any] | None,
    weather_codes: list[Any],
    start: datetime,
) -> list[dict[str, float | int | None]]:
    time_to_index = {str(value): index for index, value in enumerate(hourly_times)}
    values: list[dict[str, float | int | None]] = []

    # Open-Meteo's precipitation value at HH:00 represents the preceding hour.
    # Therefore, the interval start..start+1h is represented by the value at start+1h.
    for offset in range(1, 7):
        interval_end = start + timedelta(hours=offset)
        key = interval_end.strftime("%Y-%m-%dT%H:%M")
        index = time_to_index.get(key)
        if index is None:
            raise ValueError(f"Open-Meteo forecast is missing {key}")

        raw_amount = precipitation[index]
        amount = float(raw_amount) if raw_amount is not None else 0.0
        probability: float | None = None
        if precipitation_probability is not None:
            raw_probability = precipitation_probability[index]
            probability = float(raw_probability) if raw_probability is not None else None
        raw_weather_code = weather_codes[index]
        weather_code = int(raw_weather_code) if raw_weather_code is not None else 0
        values.append(
            {
                "precipitation": amount,
                "probability": probability,
                "weather_code": weather_code,
            }
        )

    return values


def _max_or_none(values: Any) -> float | None:
    numeric = [value for value in values if value is not None]
    return max(numeric) if numeric else None


def _rain_icon(
    values: list[dict[str, float | int | None]], settings: dict[str, Any]
) -> str:
    max_precipitation = max(item["precipitation"] for item in values)
    if any(item["weather_code"] in {71, 73, 75, 77, 85, 86} for item in values):
        return "❄️"
    if max_precipitation <= settings["no_rain_max_mm_per_hour"]:
        if any(item["weather_code"] == 3 for item in values):
            return "☁️"
        return "☀️"
    if max_precipitation <= settings["light_rain_max_mm_per_hour"]:
        return "🌂"
    return "☂️"


def _period_label(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return f"{start.hour}～{end.hour}時"
    return f"{start.hour}～翌{end.hour}時"


def _build_daily_forecast(
    dates: list[Any], weather_codes: list[Any], today: date
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_date, raw_code in zip(dates, weather_codes):
        try:
            day = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Invalid daily forecast date: {raw_date}") from exc
        if day < today:
            continue
        code = int(raw_code)
        items.append(
            {
                "date": day.isoformat(),
                "month": day.month,
                "day": day.day,
                "weekday": WEEKDAY_NAMES_JA[day.weekday()],
                "icon": WEATHER_ICONS.get(code, "❓"),
            }
        )
        if len(items) == 7:
            break

    if len(items) < 7:
        raise ValueError("Open-Meteo daily forecast contains fewer than 7 days")
    return items
