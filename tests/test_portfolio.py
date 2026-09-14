from fastapi.testclient import TestClient

from agentic_flow.calyx_pipeline import profit_factor, wilson_interval
from website.main import app


def test_portfolio_site_and_health() -> None:
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    assert "Agentic Trading Research" in page.text
    assert client.get("/health").json()["status"] == "ok"


def test_public_statistics_helpers() -> None:
    assert profit_factor([3.0, -1.0, 2.0]) == 5.0
    low, high = wilson_interval(7, 10)
    assert 0.0 < low < 0.7 < high < 1.0

