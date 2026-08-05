import fakeredis
import pytest

from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.cold_start import ColdStartManager


@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_stays_in_cold_start_and_buffers_features(redis_client):
    detector = BehavioralAnomalyDetector()
    manager = ColdStartManager(redis_client, detector, cold_start_seconds=90)

    manager.handle([0.5, 0.5, 40.0])

    assert manager.is_in_cold_start() is True
    assert manager.is_ready() is False
    assert redis_client.llen("behavioral:baseline") == 1


def test_finishes_cold_start_and_trains_model_after_window(redis_client):
    detector = BehavioralAnomalyDetector()
    manager = ColdStartManager(redis_client, detector, cold_start_seconds=90)

    for _ in range(6):
        manager.handle([0.5, 0.5, 40.0])
    assert manager.is_ready() is False  # hâlâ cold start içinde, yeterli süre geçmedi

    manager.start_time -= 1000  # cold start süresinin dolduğunu simüle ediyor
    manager.handle([0.5, 0.5, 40.0])

    assert manager.is_ready() is True
    assert detector._is_fitted is True


def test_extends_window_if_not_enough_baseline_samples(redis_client):
    detector = BehavioralAnomalyDetector()
    manager = ColdStartManager(redis_client, detector, cold_start_seconds=90)
    manager.start_time -= 1000  # süre dolmuş ama hiç baseline toplanmamış

    manager.handle([0.5, 0.5, 40.0])

    assert manager.is_ready() is False
    assert detector._is_fitted is False
    # yeterli örnek yoktu, süre uzatıldı - tekrar cold start'ta olmalı
    assert manager.is_in_cold_start() is True
