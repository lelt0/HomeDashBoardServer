from home_dashboard.dashboard.layout import load_layout


def test_layout_has_tiles() -> None:
    layout = load_layout()
    assert layout["dashboard"]["columns"] == 4
    assert [tile["id"] for tile in layout["tiles"]] == [
        "weather",
        "trash",
        "habits",
        "scroll",
    ]
