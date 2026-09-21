from fastapi.testclient import TestClient

from home_dashboard.main import app

client = TestClient(app)


def test_home_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Home Dashboard" in response.text
    assert "習慣ログ" in response.text
    assert "６時間天気" in response.text
    assert "display-power-save-marquee" in response.text


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_habits_has_no_separate_feature_page() -> None:
    response = client.get("/page/habits")
    assert response.status_code == 404


def test_unknown_feature_page() -> None:
    response = client.get("/page/unknown")
    assert response.status_code == 404
