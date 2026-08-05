import fakeredis
import pytest

from app.services.traffic_window import ClientTrafficWindow


@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_empty_window_returns_zero_vector(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=60)
    assert window.feature_vector("client_a", now=1000.0) == [0.0, 0.0, 0.0]


def test_single_endpoint_gives_low_diversity(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=60)
    t0 = 1000.0
    for i in range(10):
        window.record("client_a", "/v1/accounts", latency_ms=50, timestamp=t0 + i)

    vector = window.feature_vector("client_a", now=t0 + 10)
    request_rate, endpoint_diversity, avg_latency = vector
    assert endpoint_diversity == pytest.approx(1 / 10)
    assert avg_latency == pytest.approx(50)
    assert request_rate > 0


def test_varied_endpoints_give_high_diversity(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=60)
    t0 = 2000.0
    endpoints = ["/v1/accounts", "/v1/payments"]
    for i in range(10):
        window.record("client_b", endpoints[i % 2], latency_ms=40, timestamp=t0 + i)

    vector = window.feature_vector("client_b", now=t0 + 10)
    assert vector[1] == pytest.approx(2 / 10)


def test_events_outside_window_are_excluded(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=30)
    window.record("client_c", "/v1/accounts", latency_ms=50, timestamp=1000.0)
    # 60 saniye sonra, pencere (30s) dışında kalmış olmalı
    vector = window.feature_vector("client_c", now=1060.0)
    assert vector == [0.0, 0.0, 0.0]
