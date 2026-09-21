from copy import deepcopy
from pathlib import Path
from typing import Any
import tomllib

from home_dashboard.features.registry import FeatureDefinition, get_feature

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "dashboard.toml"


def load_layout(
    layout_data: dict[str, Any] | None = None,
    feature_registry: dict[str, FeatureDefinition] | None = None,
) -> dict[str, Any]:
    """Load a dashboard layout and attach feature-specific view metadata."""
    if layout_data is None:
        with CONFIG_PATH.open("rb") as file:
            layout = tomllib.load(file)
    else:
        layout = deepcopy(layout_data)

    styles: list[str] = []
    scripts: list[str] = []

    for tile in layout["tiles"]:
        if feature_registry is None:
            feature = get_feature(tile["feature"])
        else:
            try:
                feature = feature_registry[tile["feature"]]
            except KeyError as exc:
                raise ValueError(f"Unknown feature: {tile['feature']}") from exc

        tile["title"] = feature.title
        tile["template"] = feature.template
        if feature.context_factory is not None:
            tile["context"] = feature.context_factory()
        else:
            tile.pop("context", None)

        for asset in feature.styles:
            if asset not in styles:
                styles.append(asset)
        for asset in feature.scripts:
            if asset not in scripts:
                scripts.append(asset)

    layout["assets"] = {"styles": styles, "scripts": scripts}
    return layout
