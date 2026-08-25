"""
GET/PUT /settings/thresholds endpoint'lerini gerçek FastAPI TestClient ile doğruluyor.
app.main'deki singleton detector'ların .redis referansı fakeredis'e yönlendiriliyor ki
testler gerçek bir Redis/Docker olmadan da güvenle çalışabilsin (ThresholdSettingsService
zaten Redis'e ulaşamazsa import anında çökmüyor, ama gerçek okuma/yazma için yine de
bir Redis client gerekiyor).
"""
from __future__ import annotations

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.main import app, behavioral_detector, performance_detector, threshold_settings


@pytest.fixture
def client():
    fake_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    performance_detector.redis = fake_redis
    threshold_settings.redis = fake_redis
    # testler arası sızmayı önlemek için singleton ları varsayılana sıfırlamak icin
    performance_detector.threshold = 3.2
    behavioral_detector.contamination = 0.05
    with TestClient(app) as test_client:
        yield test_client


def test_get_thresholds_returns_current_values(client):
    response =client.get("/settings/thresholds")

    assert response.status_code == 200
    body =response.json()
    assert body["z_score_threshold"] == pytest.approx(3.2)
    assert body["contamination"]== pytest.approx(0.05)
    assert body["alert_counts_last_24h"] == {"Performans": 0, "Davranışsal": 0}


def test_put_thresholds_updates_values_and_persists(client):
    response = client.put("/settings/thresholds", json={"z_score_threshold": 4.0, "contamination": 0.15})

    assert response.status_code == 200
    body = response.json()
    assert body["z_score_threshold"] == 4.0
    assert body["contamination"] == 0.15

    follow_up = client.get("/settings/thresholds")
    assert follow_up.json()["z_score_threshold"] == 4.0
    assert performance_detector.threshold == 4.0


def test_put_thresholds_partial_update_leaves_other_value_unchanged(client):
    client.put("/settings/thresholds", json={"z_score_threshold": 4.0})

    response = client.get("/settings/thresholds")

    assert response.json()["z_score_threshold"] == 4.0
    assert response.json()["contamination"] == pytest.approx(0.05)


def test_put_thresholds_rejects_invalid_contamination(client):
    response = client.put("/settings/thresholds", json={"contamination": 0.9})

    assert response.status_code == 422
