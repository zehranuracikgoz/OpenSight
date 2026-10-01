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

    manager.handle("c1", [0.5, 0.5, 40.0], 1000.0)

    assert manager.is_in_cold_start() is True
    assert manager.is_ready() is False
    assert redis_client.llen("behavioral:baseline:v2") == 1


def test_finishes_cold_start_and_trains_model_after_window(redis_client):
    detector = BehavioralAnomalyDetector()
    manager = ColdStartManager(redis_client, detector, cold_start_seconds=90)

    for i in range(30):
        manager.handle("c1", [0.5, 0.5, 40.0], 1000.0 + i * 10)  # seyreltme aralığından (5s) seyrek
    assert manager.is_ready() is False  # hâlâ cold start içinde, yeterli süre geçmedi

    manager.start_time -= 1000  # cold start süresinin dolduğunu simüle ediyor
    manager.handle("c1", [0.5, 0.5, 40.0], 2000.0)

    assert manager.is_ready() is True
    assert detector._is_fitted is True


def test_extends_window_if_not_enough_baseline_samples(redis_client):
    detector = BehavioralAnomalyDetector()
    manager = ColdStartManager(redis_client, detector, cold_start_seconds=90)
    manager.start_time -= 1000  # süre dolmuş ama hiç baseline toplanmamış

    manager.handle("c1", [0.5, 0.5, 40.0], 1000.0)

    assert manager.is_ready() is False
    assert detector._is_fitted is False
    # yeterli örnek yoktu, süre uzatıldı - tekrar cold start'ta olmalı
    assert manager.is_in_cold_start() is True


def test_resumes_immediately_when_persisted_baseline_already_sufficient(redis_client):
    for _ in range(30):
        redis_client.rpush("behavioral:baseline:v2", "0.5,0.5,40.0")
    detector = BehavioralAnomalyDetector()

    manager = ColdStartManager(redis_client, detector, cold_start_seconds=90)

    assert manager.is_ready() is True
    assert manager.is_in_cold_start() is False
    assert detector._is_fitted is True


def test_does_not_resume_when_persisted_baseline_insufficient(redis_client):
    for _ in range(10):
        redis_client.rpush("behavioral:baseline:v2", "0.5,0.5,40.0")
    detector = BehavioralAnomalyDetector()

    manager = ColdStartManager(redis_client, detector, cold_start_seconds=90)

    assert manager.is_ready() is False
    assert manager.is_in_cold_start() is True
    assert detector._is_fitted is False


def test_starts_normal_cold_start_when_redis_unreachable_at_startup():
    from unittest.mock import MagicMock
    from redis.exceptions import ConnectionError as RedisConnectionError

    broken_redis = MagicMock()
    broken_redis.lrange.side_effect = RedisConnectionError("bağlantı yok")
    detector = BehavioralAnomalyDetector()

    manager = ColdStartManager(broken_redis, detector, cold_start_seconds=90)  # çökmemeli

    assert manager.is_ready() is False
    assert manager.is_in_cold_start() is True
    assert detector._is_fitted is False


def test_baseline_size_reports_persisted_sample_count(redis_client):
    for _ in range(7):
        redis_client.rpush("behavioral:baseline:v2", "0.5,0.5,40.0")
    manager = ColdStartManager(redis_client, BehavioralAnomalyDetector(), cold_start_seconds=90)

    assert manager.baseline_size() == 7


def test_baseline_sampling_is_thinned_per_client(redis_client):
    manager = ColdStartManager(redis_client, BehavioralAnomalyDetector(), cold_start_seconds=90, baseline_min_gap_seconds=5.0)

    # yoğun istemci saniyede birkaç vektör üretiyor ama 5 sn'de sadece biri baseline'a giriyor
    for i in range(20):
        manager.handle("busy", [1.0, 0.5, 100.0], 1000.0 + i * 0.5)  # 10 sn boyunca, 0.5 sn arayla

    assert redis_client.llen("behavioral:baseline:v2") == 2  # t=1000 ve t=1005


def test_thinning_does_not_starve_slow_client_of_baseline_weight(redis_client):
    manager = ColdStartManager(redis_client, BehavioralAnomalyDetector(), cold_start_seconds=90, baseline_min_gap_seconds=5.0)

    for i in range(100):
        manager.handle("busy", [1.0, 0.5, 100.0], 1000.0 + i * 0.1)  # 10 sn'de 100 vektör
    for i in range(2):
        manager.handle("slow", [0.05, 1.0, 80.0], 1000.0 + i * 20)  # 20 sn arayla

    rows = redis_client.lrange("behavioral:baseline:v2", 0, -1)
    slow_rows = [r for r in rows if r.startswith("0.05")]
    assert len(slow_rows) == 2  # yavaş istemcinin her örneği giriyor
    assert len(rows) - len(slow_rows) == 2  # yoğun istemci 100 yerine 2 örnekle sınırlı


def test_thinning_is_tracked_independently_per_client(redis_client):
    manager = ColdStartManager(redis_client, BehavioralAnomalyDetector(), cold_start_seconds=90, baseline_min_gap_seconds=5.0)

    manager.handle("a", [0.5, 0.5, 40.0], 1000.0)
    manager.handle("b", [0.5, 0.5, 40.0], 1000.5)  # farklı istemci, aralık şartına takılmamalı

    assert redis_client.llen("behavioral:baseline:v2") == 2


def test_records_baseline_scale_from_simulator_active_scale_on_fresh_fit(redis_client):
    redis_client.set("simulator:active_scale", "0.02")
    manager = ColdStartManager(redis_client, BehavioralAnomalyDetector(), cold_start_seconds=90)
    for i in range(30):
        manager.handle("c1", [0.5, 0.5, 40.0], 1000.0 + i * 10)
    manager.start_time -= 1000
    manager.handle("c1", [0.5, 0.5, 40.0], 2000.0)

    assert manager.baseline_scale() == pytest.approx(0.02)


def test_baseline_scale_is_none_when_simulator_never_reported_it(redis_client):
    manager = ColdStartManager(redis_client, BehavioralAnomalyDetector(), cold_start_seconds=90)
    for i in range(30):
        manager.handle("c1", [0.5, 0.5, 40.0], 1000.0 + i * 10)
    manager.start_time -= 1000
    manager.handle("c1", [0.5, 0.5, 40.0], 2000.0)

    assert manager.baseline_scale() is None


def test_baseline_scale_none_when_baseline_never_collected(redis_client):
    manager = ColdStartManager(redis_client, BehavioralAnomalyDetector(), cold_start_seconds=90)

    assert manager.baseline_scale() is None
