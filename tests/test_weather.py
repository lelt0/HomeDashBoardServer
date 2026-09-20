from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json

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
            "light_rain": "#10191b",
            "rain": "#0f1820",
        },
    }
    settings.update(overrides)
    return settings


def test_weather_icon_is_based_only_on_weather_code() -> None:
    sunny_with_heavy_rain = [
        {"precipitation": 5.0, "probability": 100.0, "weather_code": 0}
    ]
    assert weather_module._weather_icon(sunny_with_heavy_rain) == "☀️"
    assert weather_module._weather_icon(
        [{"precipitation": 0.0, "probability": 0.0, "weather_code": 3}]
    ) == "☁️"
    assert weather_module._weather_icon(
        [{"precipitation": 0.0, "probability": 0.0, "weather_code": 61}]
    ) == "🌧️"
    assert weather_module._weather_icon(
        [{"precipitation": 0.0, "probability": 0.0, "weather_code": 71}]
    ) == "🌨️"
    assert weather_module._weather_icon(
        [{"precipitation": 0.0, "probability": 0.0, "weather_code": 95}]
    ) == "⛈️"


def test_background_state_is_based_only_on_precipitation() -> None:
    settings = _settings()
    assert weather_module._background_state(
        [{"precipitation": 0.0, "probability": 0.0, "weather_code": 61}], settings
    ) == "sunny"
    assert weather_module._background_state(
        [{"precipitation": 0.1, "probability": 0.0, "weather_code": 0}], settings
    ) == "light_rain"
    assert weather_module._background_state(
        [{"precipitation": 2.0, "probability": 0.0, "weather_code": 0}], settings
    ) == "light_rain"
    assert weather_module._background_state(
        [{"precipitation": 2.1, "probability": 0.0, "weather_code": 0}], settings
    ) == "rain"

    custom = _settings(no_rain_max_mm_per_hour=0.2, light_rain_max_mm_per_hour=3.5)
    assert weather_module._background_state(
        [{"precipitation": 0.2, "probability": 0.0, "weather_code": 0}], custom
    ) == "sunny"
    assert weather_module._background_state(
        [{"precipitation": 0.21, "probability": 0.0, "weather_code": 0}], custom
    ) == "light_rain"
    assert weather_module._background_state(
        [{"precipitation": 3.5, "probability": 0.0, "weather_code": 0}], custom
    ) == "light_rain"
    assert weather_module._background_state(
        [{"precipitation": 3.51, "probability": 0.0, "weather_code": 0}], custom
    ) == "rain"


def test_background_colors_can_be_supplied_without_loading_project_config() -> None:
    settings = _settings(
        background={
            "sunny": "#000000",
            "light_rain": "#222222",
            "rain": "#333333",
        }
    )
    assert settings["background"]["sunny"] == "#000000"
    assert settings["background"]["light_rain"] == "#222222"
    assert settings["background"]["rain"] == "#333333"


def test_load_settings_uses_the_supplied_temporary_config(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "weather.toml"
    config_path.write_text(
        """[weather]
region = "一時テスト地域"
latitude = 34.5
longitude = 135.5
no_rain_max_mm_per_hour = 0.1
light_rain_max_mm_per_hour = 2.5

[weather.background]
sunny = "#000000"
light_rain = "#020202"
rain = "#030303"
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(weather_module, "CONFIG_PATH", config_path)

    settings = weather_module._load_settings()

    assert settings["region"] == "一時テスト地域"
    assert settings["latitude"] == 34.5
    assert settings["longitude"] == 135.5
    assert settings["no_rain_max_mm_per_hour"] == 0.1
    assert settings["light_rain_max_mm_per_hour"] == 2.5
    assert settings["background"]["rain"] == "#030303"


def test_period_label_crosses_midnight() -> None:
    start = datetime(2026, 9, 18, 23, tzinfo=JST)
    assert weather_module._period_label(start, start.replace(day=19, hour=5)) == "23～翌5時"


def test_period_label_same_day() -> None:
    start = datetime(2026, 9, 18, 13, tzinfo=JST)
    assert weather_module._period_label(start, start.replace(hour=19)) == "13～19時"


def test_hour_label() -> None:
    assert weather_module._hour_label(datetime(2026, 9, 18, 13, tzinfo=JST)) == "13時台"
    assert weather_module._hour_label(datetime(2026, 9, 19, 0, tzinfo=JST)) == "0時台"


def test_extract_six_hour_values_aligns_weather_code_to_hour_start() -> None:
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
    weather_codes = [0, 2, 3, 61, 71, 0, 0]
    values = weather_module._extract_six_hour_values(
        times, precipitation, probability, weather_codes, start
    )

    assert [item["precipitation"] for item in values] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert [item["probability"] for item in values] == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    assert [item["weather_code"] for item in values] == [0, 2, 3, 61, 71, 0]


def test_build_display_data_returns_six_hour_details_only() -> None:
    fetched_at = datetime(2026, 9, 18, 13, 25, tzinfo=JST)
    hourly_times = [
        f"2026-09-18T{hour:02d}:00" for hour in range(13, 20)
    ]
    payload = {
        "hourly": {
            "time": hourly_times,
            "precipitation": [0.0, 0.0, 0.5, 1.0, 2.1, 0.0, 0.0],
            "precipitation_probability": [10, 20, 30, 40, 50, 60, 70],
            "weather_code": [0, 2, 3, 61, 71, 0, 0],
        }
    }

    data = weather_module._build_display_data(payload, _settings(), fetched_at)

    assert data["region"] == "テスト地域"
    assert data["period"]["label"] == "13～19時"
    assert data["current"]["icon"] == "🌨️"
    assert data["current"]["background_state"] == "rain"
    assert data["current"]["max_precipitation_mm_per_hour"] == 2.1
    assert data["current"]["max_precipitation_probability"] == 70.0
    assert len(data["hours"]) == 6
    assert [item["label"] for item in data["hours"]] == [
        "13時台",
        "14時台",
        "15時台",
        "16時台",
        "17時台",
        "18時台",
    ]
    assert [item["icon"] for item in data["hours"]] == [
        "☀️",
        "⛅️",
        "☁️",
        "🌧️",
        "🌨️",
        "☀️",
    ]
    assert [item["precipitation_mm_per_hour"] for item in data["hours"]] == [
        0.0,
        0.5,
        1.0,
        2.1,
        0.0,
        0.0,
    ]
    assert [item["precipitation_probability"] for item in data["hours"]] == [
        20.0,
        30.0,
        40.0,
        50.0,
        60.0,
        70.0,
    ]
    assert "daily" not in data


def test_build_display_data_rejects_missing_hourly_data() -> None:
    try:
        weather_module._build_display_data({}, _settings(), datetime.now(JST))
    except ValueError as exc:
        assert "hourly" in str(exc)
    else:
        raise AssertionError("missing hourly data must fail")


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_forecast_request_fetches_only_hourly_data() -> None:
    captured_request = {}

    def fake_urlopen(request, timeout):
        captured_request["request"] = request
        captured_request["timeout"] = timeout
        return _FakeResponse({"hourly": {"time": []}})

    weather_module._fetch_forecast(_settings(), fake_urlopen)

    query = parse_qs(urlparse(captured_request["request"].full_url).query)
    assert query["hourly"] == ["precipitation,precipitation_probability,weather_code"]
    assert query["forecast_hours"] == ["7"]
    assert query["timezone"] == [weather_module.TIMEZONE_NAME]
    assert "daily" not in query
    assert "forecast_days" not in query


def test_weather_endpoint_returns_forecast_without_project_settings(monkeypatch) -> None:
    now = datetime.now(weather_module.JST)
    start = now.replace(minute=0, second=0, microsecond=0)
    hourly_times = [
        (start + weather_module.timedelta(hours=offset)).strftime("%Y-%m-%dT%H:%M")
        for offset in range(7)
    ]
    payload = {
        "hourly": {
            "time": hourly_times,
            "precipitation": [0.0] * 7,
            "precipitation_probability": [5] * 7,
            "weather_code": [3] * 7,
        }
    }
    test_settings = _settings(region="テスト地域")
    monkeypatch.setattr(weather_module, "_load_settings", lambda: test_settings)
    monkeypatch.setattr(weather_module, "_fetch_forecast", lambda settings: payload)
    weather_module.CACHE = weather_module.WeatherCache()

    result = weather_module.get_weather()

    assert result["ok"] is True
    assert result["data"]["region"] == "テスト地域"
    assert len(result["data"]["hours"]) == 6
    assert result["data"]["current"]["icon"] == "☁️"
    assert result["data"]["current"]["background_state"] == "sunny"
    assert "daily" not in result["data"]


def test_weather_template_contains_hourly_detail_without_daily_forecast() -> None:
    html = Path("web/templates/features/weather.html").read_text(encoding="utf-8")
    js = Path("web/static/features/weather/weather.js").read_text(encoding="utf-8")
    css = Path("web/static/features/weather/weather.css").read_text(encoding="utf-8")

    assert 'data-role="hours"' in html
    assert 'data-bg-cloudy' not in html
    assert "1週間" not in html
    assert "daily" not in html
    assert "feature-weather__days" not in css
    assert "feature-weather__day" not in css
    assert ".feature-weather__chart-wrap" in css
    assert "display: flex;" in css
    assert ".feature-weather__hours" in css
    assert "renderDays" not in js
    assert "data-role=\"days\"" not in js
    assert "daily" not in js
    assert "setRainClass" not in js
    assert "data-bg-cloudy" not in js
