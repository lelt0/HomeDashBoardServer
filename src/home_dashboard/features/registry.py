from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter

from home_dashboard.features.trash import load_feature_context
from home_dashboard.features.weather import load_feature_context as load_weather_feature_context
from home_dashboard.features.weather import router as weather_router


@dataclass(frozen=True)
class FeatureDefinition:
    title: str
    template: str
    styles: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    page_template: str | None = None
    context_factory: Callable[[], dict[str, Any]] | None = None
    router: APIRouter | None = None


FEATURES: dict[str, FeatureDefinition] = {
    "clock": FeatureDefinition(
        title="時刻",
        template="features/clock.html",
        styles=("/static/features/clock/clock.css",),
        scripts=("/static/features/clock/clock.js",),
    ),
    "interaction": FeatureDefinition(
        title="タッチ操作",
        template="features/interaction.html",
        styles=("/static/features/interaction/interaction.css",),
        scripts=("/static/features/interaction/interaction.js",),
        page_template="pages/features/interaction.html",
    ),
    "scroll": FeatureDefinition(
        title="スクロール",
        template="features/scroll.html",
    ),
    "placeholder": FeatureDefinition(
        title="Home Dashboard",
        template="features/placeholder.html",
        styles=("/static/features/navigation/navigation.css",),
        scripts=("/static/features/navigation/tile-navigation.js",),
        page_template="pages/features/placeholder.html",
    ),
    "weather": FeatureDefinition(
        title="６時間天気",
        template="features/weather.html",
        styles=("/static/features/weather/weather.css",),
        scripts=("/static/features/weather/weather.js",),
        context_factory=load_weather_feature_context,
        router=weather_router,
    ),
    "trash": FeatureDefinition(
        title="ゴミ回収日",
        template="features/trash.html",
        styles=("/static/features/trash/trash.css",),
        scripts=("/static/features/trash/trash.js",),
        context_factory=load_feature_context,
    ),
}


def get_feature(feature_id: str) -> FeatureDefinition:
    try:
        return FEATURES[feature_id]
    except KeyError as exc:
        raise ValueError(f"Unknown feature: {feature_id}") from exc
