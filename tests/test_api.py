"""Проверки контракта, сохранения результатов и границ модели."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import risk
from app.schemas.prediction import FarmRequest
from app.services.scoring import get_risk_level

PAYLOAD = {
    "farm_id": "FARM-101",
    "region": "Rostov",
    "crop_type": "sunflower",
    "area_ha": 1200,
    "temperature_avg": 38,
    "precipitation_mm": 80,
    "payment_delay_days": 45,
    "previous_defaults": 1,
    "debt": 6_500_000,
}


@pytest.fixture
def client():
    """Каждый тест использует отдельное приложение и пустое хранилище."""
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_and_model_info(client):
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/model-info")
    assert response.status_code == 200
    assert response.json()["model_version"] == "1.1"


def test_prediction_roundtrip(client):
    response = client.post("/predict", json=PAYLOAD)
    assert response.status_code == 201
    result = response.json()
    assert result["risk_score"] == 1.0
    assert result["risk_level"] == "high"
    assert result["farm_id"] == PAYLOAD["farm_id"]
    assert client.get(response.headers["Location"]).json() == result
    assert float(response.headers["X-Process-Time"]) >= 0


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"area_ha": -100}, 422),
        ({"region": "Moscow"}, 400),
        ({"temperature_avg": 61}, 422),
        ({"farm_id": "   "}, 422),
    ],
)
def test_invalid_body(client, updates, code):
    response = client.post("/predict", json=PAYLOAD | updates)
    assert response.status_code == code
    assert client.get("/predictions").json() == []


def test_missing_field(client):
    payload = PAYLOAD.copy()
    del payload["debt"]
    assert client.post("/predict", json=payload).status_code == 422


def test_not_found(client):
    assert client.get("/predictions/unknown-id").status_code == 404


@pytest.mark.parametrize("query", ["limit=-5", "limit=101", "risk_level=extreme"])
def test_invalid_query(client, query):
    assert client.get(f"/predictions?{query}").status_code == 422


def test_recent_and_filtered(client):
    high = client.post("/predict", json=PAYLOAD).json()
    low_payload = PAYLOAD | {
        "temperature_avg": 20,
        "precipitation_mm": 200,
        "payment_delay_days": 0,
        "previous_defaults": 0,
        "debt": 0,
    }
    low = client.post("/predict", json=low_payload).json()
    medium = client.post(
        "/predict", json=low_payload | {"payment_delay_days": 45}
    ).json()
    assert client.get("/predictions?limit=2").json() == [medium, low]
    assert client.get("/predictions?risk_level=high").json() == [high]
    assert client.get("/predictions?risk_level=medium&limit=5").json() == [medium]


def test_unavailable_model(client, monkeypatch):
    monkeypatch.setattr(risk, "MODEL_READY", False)
    assert client.post("/predict", json=PAYLOAD).status_code == 503
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/model-info").json()["status"] == "unavailable"
    assert client.get("/predictions").json() == []
    # Структурная валидация выполняется еще до проверки готовности модели.
    assert client.post("/predict", json=PAYLOAD | {"area_ha": -1}).status_code == 422


@pytest.mark.parametrize(
    ("score", "level"),
    [(0.29, "low"), (0.3, "medium"), (0.69, "medium"), (0.7, "high")],
)
def test_risk_boundaries(score, level):
    assert get_risk_level(score) == level


@pytest.mark.parametrize(
    ("temperature", "score"), [(5, 0.1), (35, 0.1), (4, 0.15), (36, 0.15)]
)
def test_temperature_rule(temperature, score):
    data = FarmRequest(
        **(
            PAYLOAD
            | {
                "temperature_avg": temperature,
                "precipitation_mm": 200,
                "payment_delay_days": 0,
                "previous_defaults": 0,
                "debt": 0,
            }
        )
    )
    assert risk.calculate_risk(data) == score


def test_openapi(client):
    spec = client.get("/openapi.json").json()
    assert set(spec["paths"]) == {
        "/health",
        "/model-info",
        "/predict",
        "/predictions",
        "/predictions/{request_id}",
    }
    assert {"201", "400", "422", "503"} <= set(
        spec["paths"]["/predict"]["post"]["responses"]
    )
    assert "404" in spec["paths"]["/predictions/{request_id}"]["get"]["responses"]
