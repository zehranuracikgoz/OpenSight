"""
uçtan uca entegrasyon testi: gerçek RabbitMQ + Redis container'ları (testcontainers) ile,
backend'in yayınladığı formatta bir TrafficEvent mesajı publish edip RabbitMqTrafficConsumer'ın
bunu gerçekten tükettiğini, Redis'e yazdığını ve cold start akışının çalıştığını doğruluyor.
birim testlerinden ayrı dosyada - Docker gerektirir, CI'da ayrı çalıştırılabilir.
"""
from __future__ import annotations

import json
import threading
import time

import pika
import pytest
from testcontainers.community.rabbitmq import RabbitMqContainer
from testcontainers.community.redis import RedisContainer

from app.messaging.rabbitmq_consumer import EXCHANGE_NAME, RabbitMqTrafficConsumer
from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.cold_start import ColdStartManager
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

    connection_params = rabbitmq_container.get_connection_params()
    consumer = RabbitMqTrafficConsumer(
        connection_params.host,
        performance_detector,
        traffic_window,
        cold_start,
        port=connection_params.port,
    )

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
