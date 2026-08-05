"""
uçtan uca entegrasyon testi: gerçek RabbitMQ + Redis container'ları (testcontainers) ile,
backend'in yayınladığı formatta bir TrafficEvent mesajı publish edip RabbitMqTrafficConsumer'ın
bunu gerçekten tükettiğini, Redis'e yazdığını, cold start akışının ve anomali tetiklendiğinde
backend'e (mock'lanmış) yazma çağrısının çalıştığını doğruluyor. Backend'in kendisi mock'lanıyor
- gerçek bir ASP.NET Core sunucusu bu testte ayağa kaldırılmıyor (bkz. rapor notu).
birim testlerinden ayrı dosyada - Docker gerektirir, CI'da ayrı çalıştırılabilir.
"""
from __future__ import annotations

import json
import threading
import time
from unittest.mock import MagicMock

import pika
import pytest
from testcontainers.community.rabbitmq import RabbitMqContainer
from testcontainers.community.redis import RedisContainer

from app.messaging.rabbitmq_consumer import EXCHANGE_NAME, RabbitMqTrafficConsumer
from app.services.anomaly_pipeline import AnomalyPipeline
from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.cold_start import ColdStartManager
from app.services.correlation_engine import CorrelationEngine
from app.services.performance_detector import RollingZScoreDetector
from app.services.traffic_window import ClientTrafficWindow


@pytest.fixture(scope="module")
def rabbitmq_container():
    with RabbitMqContainer("rabbitmq:3-management-alpine") as container:
        yield container


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as container:
        yield container


def _publish_events(connection_params, events):
    """(client_id, endpoint, latency_ms) listesini backend formatında, tek bir bağlantı üzerinden yayınlıyor"""
    connection = pika.BlockingConnection(connection_params)
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)
        for client_id, endpoint, latency_ms in events:
            body = json.dumps({
                "ClientId": client_id,
                "Endpoint": endpoint,
                "LatencyMs": latency_ms,
                "StatusCode": 200,
            })
            channel.basic_publish(exchange=EXCHANGE_NAME, routing_key="traffic.raw", body=body)
    finally:
        connection.close()


@pytest.fixture(scope="module")
def pipeline(rabbitmq_container, redis_container):
    redis_client = redis_container.get_client()
    performance_detector = RollingZScoreDetector(redis_client, window_size=20, threshold=3.0)
    behavioral_detector = BehavioralAnomalyDetector()
    traffic_window = ClientTrafficWindow(redis_client, window_seconds=60)
    cold_start = ColdStartManager(redis_client, behavioral_detector, cold_start_seconds=90)
    correlation_engine = CorrelationEngine(window_seconds=1800)
    backend_client = MagicMock()
    backend_client.post_alert.return_value = "alert-stub"
    backend_client.post_correlation.return_value = "corr-stub"

    anomaly_pipeline = AnomalyPipeline(
        performance_detector, behavioral_detector, traffic_window, cold_start, correlation_engine, backend_client
    )

    connection_params = rabbitmq_container.get_connection_params()
    consumer = RabbitMqTrafficConsumer(connection_params.host, anomaly_pipeline, port=connection_params.port)

    thread = threading.Thread(target=consumer.run_forever, daemon=True)
    thread.start()
    time.sleep(2)  # consumer'ın exchange/queue kurup dinlemeye başlamasını bekle

    yield {
        "redis": redis_client,
        "connection_params": connection_params,
        "performance_detector": performance_detector,
        "behavioral_detector": behavioral_detector,
        "traffic_window": traffic_window,
        "cold_start": cold_start,
        "backend_client": backend_client,
    }

    consumer.stop()


def _wait_until(predicate, timeout=10, interval=0.2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_consumer_writes_performance_window_to_redis(pipeline):
    redis_client = pipeline["redis"]
    _publish_events(pipeline["connection_params"], [("client_x", "/v1/accounts", 50)] * 10)

    assert _wait_until(lambda: redis_client.llen("zscore:window:client_x") >= 10)


def test_consumer_writes_behavioral_window_to_redis(pipeline):
    redis_client = pipeline["redis"]
    traffic_window = pipeline["traffic_window"]

    events = [
        ("client_y", "/v1/accounts" if i % 2 == 0 else "/v1/payments", 40)
        for i in range(6)
    ]
    _publish_events(pipeline["connection_params"], events)

    assert _wait_until(lambda: redis_client.llen("behavioral:window:client_y") >= 6)

    request_rate, endpoint_diversity, avg_latency = traffic_window.feature_vector("client_y")
    assert request_rate > 0
    assert endpoint_diversity > 0
    assert avg_latency == pytest.approx(40, abs=1)


def test_cold_start_collects_baseline_via_real_pipeline(pipeline):
    redis_client = pipeline["redis"]
    cold_start = pipeline["cold_start"]

    assert cold_start.is_in_cold_start() is True

    _publish_events(pipeline["connection_params"], [("client_z", "/v1/accounts", 45)] * 5)

    assert _wait_until(lambda: redis_client.llen("behavioral:baseline") >= 5)
    assert cold_start.is_ready() is False  # süre henüz dolmadı


def test_cold_start_finishes_and_trains_model_once_window_elapses(pipeline):
    cold_start = pipeline["cold_start"]
    behavioral_detector = pipeline["behavioral_detector"]
    connection_params = pipeline["connection_params"]

    _publish_events(connection_params, [("client_w", "/v1/accounts", 45)] * 6)
    _wait_until(lambda: cold_start.redis.llen("behavioral:baseline") >= 5)

    # cold start süresinin dolduğunu simüle ediyor (gerçek akışta 90s beklenir)
    cold_start.start_time -= 1000
    _publish_events(connection_params, [("client_w", "/v1/accounts", 45)])

    assert _wait_until(lambda: cold_start.is_ready() is True)
    assert behavioral_detector._is_fitted is True


def test_performance_anomaly_through_real_queue_posts_alert_to_backend(pipeline):
    backend_client = pipeline["backend_client"]
    connection_params = pipeline["connection_params"]
    redis_client = pipeline["redis"]
    backend_client.reset_mock()

    baseline_latencies = [44, 46, 45, 47, 45, 46, 44, 47, 45, 46]  # doğal varyanslı baseline (std=0 z-score'u anlamsızlaştırır)
    _publish_events(connection_params, [("client_v", "/v1/accounts", lat) for lat in baseline_latencies])
    assert _wait_until(lambda: redis_client.llen("zscore:window:client_v") >= len(baseline_latencies))
    _publish_events(connection_params, [("client_v", "/v1/accounts", 5000)])

    # bu noktada cold start önceki testte tamamlanmış olabilir, baseline mesajlarından biri
    # bile davranışsal anomali olarak işaretlenip erken bir post_alert çağrısı yapmış olabilir -
    # bu yüzden "herhangi bir çağrı" yerine özellikle "Performans" tipli çağrıyı bekliyoruz
    def _has_performance_alert():
        return any(c.args[1] == "Performans" for c in backend_client.post_alert.call_args_list)

    assert _wait_until(_has_performance_alert)
    performance_calls = [c for c in backend_client.post_alert.call_args_list if c.args[1] == "Performans"]
    assert len(performance_calls) >= 1
    assert performance_calls[0].args[0] == "client_v"
