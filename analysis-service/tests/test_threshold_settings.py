"""
ThresholdSettingsService'in eşik değerlerini detector'lara uyguladığını, Redis'te kalıcı
tuttuğunu ve 24 saatlik alarm penceresini doğru saydığını fakeredis ile doğruluyor
"""
from __future__ import annotations

import time

import fakeredis
import pytest

from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.performance_detector import RollingZScoreDetector
from app.services.threshold_settings import ThresholdSettingsService


@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def _make_service(redis_client):
    performance_detector = RollingZScoreDetector(redis_client, window_size=20, threshold=3.2)
    behavioral_detector = BehavioralAnomalyDetector(contamination=0.05)
    service = ThresholdSettingsService(redis_client, performance_detector, behavioral_detector)
    return service, performance_detector, behavioral_detector


def test_get_settings_returns_defaults_when_nothing_persisted(redis_client):
    service, _, _ =_make_service(redis_client)

    settings = service.get_settings()

    assert settings.z_score_threshold == 3.2
    assert settings.contamination == 0.05
    assert settings.last_trained_at is None
    assert settings.alert_counts_last_24h == {"Performans": 0, "Davranışsal": 0}


def test_update_settings_applies_to_detectors_and_persists(redis_client):
    service, performance_detector, behavioral_detector = _make_service(redis_client)

    updated =service.update_settings(z_score_threshold=4.5 , contamination=0.1)

    assert performance_detector.threshold == 4.5
    assert behavioral_detector.contamination== 0.1
    assert updated.z_score_threshold == 4.5
    assert redis_client.get("settings:z_score_threshold") == "4.5"
    assert redis_client.get("settings:contamination") == "0.1"


def test_new_service_instance_picks_up_persisted_values(redis_client):
    service, _, _ = _make_service(redis_client)
    service.update_settings(z_score_threshold=5.0, contamination=0.2)

    # servis yeniden başlarsa yeni detector'larla yeni bir instance oluşturuluyor
    new_performance_detector = RollingZScoreDetector(redis_client, window_size=20, threshold=3.2)
    new_behavioral_detector = BehavioralAnomalyDetector(contamination=0.05)
    ThresholdSettingsService(redis_client, new_performance_detector, new_behavioral_detector)

    assert new_performance_detector.threshold == 5.0
    assert new_behavioral_detector.contamination ==0.2


def test_record_alert_counts_within_24_hours(redis_client):
    service, _, _ = _make_service(redis_client)

    service.record_alert("Performans")
    service.record_alert("Performans")
    service.record_alert("Davranışsal")

    settings = service.get_settings()
    assert settings.alert_counts_last_24h["Performans"] == 2
    assert settings.alert_counts_last_24h["Davranışsal"] == 1


def test_record_alert_excludes_entries_older_than_24_hours(redis_client):
    service, _, _ = _make_service(redis_client)

    # 25 saat önceki bir alarmı elle ekleyip 24 saatlik pencerenin dışında kaldığını doğruluyor
    old_timestamp = time.time() - 25 * 60 * 60
    redis_client.zadd("settings:alert_count:Performans", {str(old_timestamp): old_timestamp})

    settings = service.get_settings()
    assert settings.alert_counts_last_24h["Performans"] == 0


def test_last_trained_at_reflects_behavioral_detector_fit_time(redis_client):
    service, _, behavioral_detector = _make_service(redis_client)
    assert service.get_settings().last_trained_at is None

    behavioral_detector.fit([[0.5, 0.5 , 40.0]] * 10)

    assert service.get_settings().last_trained_at is not None