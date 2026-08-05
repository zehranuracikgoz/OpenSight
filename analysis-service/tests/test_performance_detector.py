import fakeredis
import pytest

from app.services.performance_detector import RollingZScoreDetector


@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_no_anomaly_during_cold_start(redis_client):
    det = RollingZScoreDetector(redis_client, window_size=20, threshold=3.0)
    for _ in range(3):
        result = det.update_and_score("client_a", 50)
        assert result.is_anomaly is False


def test_normal_traffic_does_not_trigger_false_positive(redis_client):
    """normal profil trafiği anomali üretmeyecek"""
    det = RollingZScoreDetector(redis_client, window_size=20, threshold=3.0)
    for latency in [48, 50, 49, 51, 50, 52, 49, 50, 48, 51, 50, 49]:
        result = det.update_and_score("client_a", latency)
    assert result.is_anomaly is False


def test_spike_triggers_anomaly(redis_client):
    """ani gecikme sıçraması anomali olarak işaretlenecek"""
    det = RollingZScoreDetector(redis_client, window_size=20, threshold=3.0)
    for latency in [48, 50, 49, 51, 50, 52, 49, 50, 48, 51, 50, 49]:
        det.update_and_score("client_a", latency)
    result = det.update_and_score("client_a", 2000)
    assert result.is_anomaly is True
    assert result.z_score > 3.0


def test_clients_are_scored_independently(redis_client):
    det = RollingZScoreDetector(redis_client, window_size=20, threshold=3.0)
    for latency in [48, 50, 49, 51, 50, 52, 49, 50, 48, 51, 50, 49]:
        det.update_and_score("client_a", latency)
    # client_b'nin hiç geçmişi yok-> anomali olarak işaretlenmeyecek(cold start koruması)
    result = det.update_and_score("client_b", 2000)
    assert result.is_anomaly is False
