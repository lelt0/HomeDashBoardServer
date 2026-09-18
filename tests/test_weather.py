from datetime import datetime, timezone
from pathlib import Path
import home_dashboard.features.weather as weather_module


JST = timezone.utc


def _settings(**overrides: object) -> dict:
    settings = {
        "region": "テスト地域",
        "latitude": 35.0,
        "longitude": 135.0,
        "no_rain_max_mm_per_hour": 0.0,
        "light_rain_max_mm_per_hour": 2.0,
        "background": {
            "sunny": "#151515",
            "cloudy": "#151515",
            "light_rain": "#10191b",
            "rain": "#0f1820",
        },
    }
    settings.update(overrides)
    return settings


def test_rain_icon_thresholds_are_configurable() -> None:
    settings = _settings()
    clear = [{"precipitation": 0.0, "probability": 0.0, "weather_code": 0}]
    cloudy = [{"precipitation": 0.0, "probability": 0.0, "weather_code": 3}]
    assert weather_module._rain_icon(clear, settings) == "☀"
    assert weather_module._rain_icon(cloudy, settings) == "☁"
    assert weather_module._rain_icon(
        [{"precipitation": 1.0, "probability": 10.0, "weather_code": 71}], settings
    ) == "❄"
    assert weather_module._rain_icon(
        [{"precipitation": 0.0, "probability": 0.0, "weather_code": 71}], settings
    ) == "❄"
    assert weather_module._rain_icon(
        [{"precipitation": 0.1, "probability": 10.0, "weather_code": 61}], settings
    ) == "🌂"
    assert weather_module._rain_icon(
        [{"precipitation": 2.0, "probability": 20.0, "weather_code": 61}], settings
    ) == "🌂"
    assert weather_module._rain_icon(
        [{"precipitation": 2.1, "probability": 30.0, "weather_code": 61}], settings
    ) == "☂"

    custom = _settings(no_rain_max_mm_per_hour=0.2, light_rain_max_mm_per_hour=3.5)
    assert weather_module._rain_icon(
        [{"precipitation": 0.2, "probability": 0.0, "weather_code": 0}], custom
    ) == "☀"
    assert weather_module._rain_icon(
        [{"precipitation": 0.21, "probability": 0.0, "weather_code": 0}], custom
    ) == "🌂"
    assert weather_module._rain_icon(
        [{"precipitation": 3.5, "probability": 0.0, "weather_code": 61}], custom
    ) == "🌂"
    assert weather_module._rain_icon(
        [{"precipitation": 3.51, "probability": 0.0, "weather_code": 61}], custom
    ) == "☂"


def test_weekend_color_is_applied_to_the_full_date_string() -> None:
    js = Path("web/static/features/weather/weather.js").read_text()
    assert "feature-weather__day-date--sat" in js
    assert "feature-weather__day-date--sun" in js
    assert "feature-weather__weekday--sat" not in js
    assert "feature-weather__weekday--sun" not in js


def test_background_colors_are_loaded() -> None:
    settings = weather_module._load_settings()
    assert settings["background"]["sunny"] == "#151515"
    assert settings["background"]["cloudy"] == "#151515"
    assert settings["background"]["light_rain"] == "#10191b"
    assert settings["background"]["rain"] == "#0f1820"


def test_period_label_crosses_midnight() -> None:
    start = datetime(2026, 9, 18, 23, tzinfo=JST)
    assert weather_module._period_label(start, start.replace(day=19, hour=5)) == "23～翌5時"


def test_period_label_same_day() -> None:
    start = datetime(2026, 9, 18, 13, tzinfo=JST)
    assert weather_module._period_label(start, start.replace(hour=19)) == "13～19時"


def test_extract_six_hour_values_uses_end_of_interval_for_precipitation() -> None:
    start = datetime(2026, 9, 18, 13, tzinfo=JST)
    times = [
        "2026-09-18T13:00",
        "2026-09-18T14:00",
        "2026-09-18T15:00",
        "2026-09-18T16:00",
        "2026-09-18T17:00",
        "2026-09-18T18:00",
        "2026-09-18T19:00",
    ]
    precipitation = [99, 1, 2, 3, 4, 5, 6]
    probability = [99, 10, 20, 30, 40, 50, 60]
    weather_codes = [0, 1, 2, 3, 61, 0, 0]
    values = weather_module._extract_six_hour_values(
        times, precipitation, probability, weather_codes, start
    )
    assert [item["precipitation"] for item in values] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert [item["probability"] for item in values] == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    assert [item["weather_code"] for item in values] == [1, 2, 3, 61, 0, 0]


def test_build_display_data_returns_seven_days() -> None:
    fetched_at = datetime(2026, 9, 18, 13, 25, tzinfo=JST)
    hourly_times = []
    precipitation = []
    probability = []
    hourly_weather_codes = []
    for hour in range(13, 24):
        hourly_times.append(f"2026-09-18T{hour:02d}:00")
        precipitation.append(0.0)
        probability.append(10)
        hourly_weather_codes.append(3)
    for hour in range(24):
        hourly_times.append(f"2026-09-19T{hour:02d}:00")
        precipitation.append(0.0)
        probability.append(10)
        hourly_weather_codes.append(3)

    payload = {
        "hourly": {
            "time": hourly_times,
            "precipitation": precipitation,
            "precipitation_probability": probability,
            "weather_code": hourly_weather_codes,
        },
        "daily": {
            "time": [
                "2026-09-18",
                "2026-09-19",
                "2026-09-20",
                "2026-09-21",
                "2026-09-22",
                "2026-09-23",
                "2026-09-24",
            ],
            "weather_code": [0, 1, 2, 3, 61, 80, 95],
        },
    }

    data = weather_module._build_display_data(payload, _settings(), fetched_at)
    assert data["region"] == "テスト地域"
    assert data["period"]["label"] == "13～19時"
    assert data["current"]["icon"] == "☁"
    assert data["current"]["max_precipitation_mm_per_hour"] == 0.0
    assert data["current"]["max_precipitation_probability"] == 10.0
    assert len(data["daily"]) == 7
    assert data["daily"][0]["icon"] == "☀️"
    assert data["daily"][-1]["icon"] == "⛈️"



def test_weather_endpoint_returns_forecast(monkeypatch) -> None:
    now = datetime.now(weather_module.JST)
    hourly_times = []
    precipitation = []
    probability = []
    hourly_weather_codes = []
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(168):
        point = start + weather_module.timedelta(hours=offset)
        hourly_times.append(point.strftime("%Y-%m-%dT%H:%M"))
        precipitation.append(0.0)
        probability.append(5)
        hourly_weather_codes.append(3)

    daily_times = [(start.date() + weather_module.timedelta(days=i)).isoformat() for i in range(7)]
    payload = {
        "hourly": {
            "time": hourly_times,
            "precipitation": precipitation,
            "precipitation_probability": probability,
            "weather_code": hourly_weather_codes,
        },
        "daily": {
            "time": daily_times,
            "weather_code": [0, 1, 2, 3, 61, 80, 95],
        },
    }
    monkeypatch.setattr(weather_module, "_fetch_forecast", lambda settings: payload)

    result = weather_module.get_weather()

    assert result["ok"] is True
    assert result["data"]["region"] == "神戸東部"
    assert len(result["data"]["daily"]) == 7
    assert result["data"]["current"]["icon"] == "☁"
