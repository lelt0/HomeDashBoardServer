from pathlib import Path
from typing import Any
import tomllib

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "dashboard.toml"


def load_layout() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as file:
        return tomllib.load(file)
