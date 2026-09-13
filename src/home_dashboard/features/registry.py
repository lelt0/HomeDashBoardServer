from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDefinition:
    title: str
    template: str
    styles: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    page_template: str | None = None


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
}


def get_feature(feature_id: str) -> FeatureDefinition:
    try:
        return FEATURES[feature_id]
    except KeyError as exc:
        raise ValueError(f"Unknown feature: {feature_id}") from exc
