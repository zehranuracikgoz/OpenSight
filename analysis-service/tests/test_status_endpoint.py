"""
GET /status: simülatör şüpheli trafiği başlatmadan önce modelin eğitilip eğitilmediğini bu
endpoint'ten soruyor. app.main'deki singleton'ların Redis/detector durumu testte kontrol ediliyor.
"""
from __future__ import annotations

import time
import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.main import app, behavioral_detector, cold_start

def _reset_singletons() -> None:
    cold_start.redis = fakeredis.FakeStrictRedis(decode_responses=True)
    cold_start._completed = False
    cold_start.start_time = time.monotonic()
    behavioral_detector._is_fitted = False
    behavioral_detector.last_trained_at = None


@pytest.fixture
def client():
    _reset_singletons()
    with TestClient(app) as test_client:
        yield test_client
    _reset_singletons()  # sonraki test dosyalarına eğitilmiş model durumu sızmasın

def test_status_reports_model_not_ready_during_cold_start(client):
    body = client.get("/status").json()

    assert body["model_ready"] is False
    assert body["in_cold_start"] is True
    assert body["baseline_samples"] ==0
    assert body["baseline_scale"] is None
    assert body["last_trained_at"] is None


def test_status_reports_model_ready_after_cold_start_completes(client):
    cold_start.redis.set("simulator:active_scale", "0.02")
    for _ in range(30):
        cold_start.redis.rpush("behavioral:baseline:v2", "0.5,0.5,40.0")
    cold_start.start_time -= 10_000  #cold start süresi dolmuş gibi
    cold_start.handle("c1", [0.5, 0.5, 40.0], time.time())

    body = client.get("/status").json()

    assert body["model_ready"] is True
    assert body["in_cold_start"] is False
    assert body["baseline_samples"] == 30
    assert body["baseline_scale"] == pytest.approx(0.02)
    assert body["last_trained_at"] is not None