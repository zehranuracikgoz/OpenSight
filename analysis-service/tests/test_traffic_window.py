import fakeredis
import pytest

from app.services.traffic_window import ClientTrafficWindow


@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_empty_window_returns_zero_vector(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=60)
    assert window.feature_vector("client_a", now=1000.0) == [0.0, 0.0, 0.0]


def test_single_endpoint_gives_full_top_endpoint_share(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=60)
    t0 = 1000.0
    for i in range(10):
        window.record("client_a", "/v1/accounts", latency_ms=50, timestamp=t0 + i)

    vector = window.feature_vector("client_a", now=t0 + 10)
    request_rate, top_endpoint_share, avg_latency = vector
    assert top_endpoint_share == pytest.approx(1.0)  # 10 isteğin 10'u aynı endpoint
    assert avg_latency == pytest.approx(50)
    assert request_rate > 0


def test_evenly_split_endpoints_give_half_top_endpoint_share(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=60)
    t0 = 2000.0
    endpoints = ["/v1/accounts", "/v1/payments"]
    for i in range(10):
        window.record("client_b", endpoints[i % 2], latency_ms=40, timestamp=t0 + i)

    vector = window.feature_vector("client_b", now=t0 + 10)
    assert vector[1] == pytest.approx(0.5)  # iki endpoint'e eşit dağılmış


def test_top_endpoint_share_uses_most_used_endpoint(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=60)
    t0 = 3000.0
    # 20 istekten 19'u /v1/accounts, 1'i /v1/payments -> en sık endpoint payı 0.95
    for i in range(20):
        endpoint = "/v1/payments" if i == 7 else "/v1/accounts"
        window.record("client_d", endpoint, latency_ms=50, timestamp=t0 + i)

    vector = window.feature_vector("client_d", now=t0 + 20)
    assert vector[1] == pytest.approx(0.95)


def test_events_outside_window_are_excluded(redis_client):
    window = ClientTrafficWindow(redis_client, window_seconds=30)
    window.record("client_c", "/v1/accounts", latency_ms=50, timestamp=1000.0)
    # 60 saniye sonra, pencere (30s) dışında kalmış olmalı
    vector = window.feature_vector("client_c", now=1060.0)
    assert vector == [0.0, 0.0, 0.0]


def test_top_endpoint_returns_name_and_share(redis_client):
    window=ClientTrafficWindow(redis_client, window_seconds=60)
    for i in range(3):
        window.record("c1", "/v1/accounts", 40, timestamp=1000.0 + i)
    window.record("c1", "/v1/payments", 40, timestamp=1004.0)

    assert window.top_endpoint("c1", now=1010.0) == ("/v1/accounts", pytest.approx(0.75))

def test_top_endpoint_is_none_for_empty_window (redis_client):
    assert ClientTrafficWindow(redis_client).top_endpoint("yok", now=1000.0) is None