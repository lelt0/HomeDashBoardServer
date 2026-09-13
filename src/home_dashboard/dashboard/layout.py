import tomllib
from pathlib import Path
from typing import Any

from home_dashboard.features.registry import get_feature

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "dashboard.toml"


def load_layout() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as file:
        layout = tomllib.load(file)

    styles: list[str] = []
    scripts: list[str] = []

    for tile in layout["tiles"]:
        feature = get_feature(tile["feature"])
        tile["title"] = feature.title
        tile["template"] = feature.template

        for asset in feature.styles:
            if asset not in styles:
                styles.append(asset)
        for asset in feature.scripts:
            if asset not in scripts:
                scripts.append(asset)

    layout["assets"] = {"styles": styles, "scripts": scripts}
    return layout
