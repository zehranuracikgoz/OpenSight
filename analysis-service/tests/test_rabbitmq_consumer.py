"""
RabbitMqTrafficConsumer'ın doğru host/port/exchange ile bağlandığını, gelen mesajları
doğru parse edip pipeline'a ilettiğini, bozuk mesajları çökmeden atladığını ve bağlantı
hatasında yeniden bağlanmayı denediğini mock'lanmış pika ile doğruluyor - gerçek bir
RabbitMQ/Docker gerektirmiyor
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.messaging.rabbitmq_consumer import EXCHANGE_NAME, RECONNECT_DELAY_SECONDS, RabbitMqTrafficConsumer


def _make_mock_channel(queue_name: str = "test-queue") -> MagicMock:
    channel = MagicMock()
    channel.queue_declare.return_value.method.queue = queue_name
    return channel


def test_connect_and_consume_uses_correct_host_port_and_exchange():
    pipeline = MagicMock()
    consumer = RabbitMqTrafficConsumer("rabbitmq-host", pipeline, port=5673)
    mock_channel = _make_mock_channel()
    mock_connection = MagicMock()
    mock_connection.channel.return_value = mock_channel

    with patch(
        "app.messaging.rabbitmq_consumer.pika.BlockingConnection", return_value=mock_connection
    ) as mock_blocking:
        consumer._connect_and_consume ()

    # BlockingConnectiona geçirilen ConnectionParameters doğru host/port taşıyor mu
    connection_params = mock_blocking.call_args[0][0]
    assert connection_params.host == "rabbitmq-host"
    assert connection_params.port == 5673

    mock_channel.exchange_declare.assert_called_once_with(
        exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True
    )
    mock_channel.queue_bind.assert_called_once_with(exchange=EXCHANGE_NAME, queue="test-queue")
    mock_channel.basic_consume.assert_called_once_with(
        queue="test-queue", on_message_callback=consumer._on_message, auto_ack=True
    )
    mock_channel.start_consuming.assert_called_once()


def test_on_message_parses_valid_payload_and_calls_pipeline():
    pipeline =MagicMock()
    consumer = RabbitMqTrafficConsumer("localhost", pipeline)
    body = json.dumps(
        {"ClientId": "client_1", "Endpoint": "/v1/accounts", "LatencyMs": 42, "StatusCode": 200}
    ).encode("utf-8")

    consumer._on_message(None, None, None, body)

    pipeline.process.assert_called_once()
    client_id, endpoint, latency_ms, timestamp = pipeline.process.call_args[0]
    assert client_id == "client_1"
    assert endpoint == "/v1/accounts"
    assert latency_ms == 42
    assert isinstance(timestamp, float)  # TrafficEventDto'da timestamp yok, varış anı kullanılıyor


def test_on_message_invalid_json_does_not_crash_or_call_pipeline():
    pipeline = MagicMock()
    consumer = RabbitMqTrafficConsumer("localhost", pipeline)

    consumer._on_message(None, None, None, b"gecersiz json")  # çökmemeli

    pipeline.process.assert_not_called()


def test_on_message_missing_field_does_not_crash_or_call_pipeline():
    pipeline = MagicMock()
    consumer = RabbitMqTrafficConsumer("localhost", pipeline)
    body = json.dumps({"ClientId": "client_1"}).encode("utf-8")  # endpoint/LatencyMs eksik

    consumer._on_message(None, None, None, body)

    pipeline.process.assert_not_called()


def test_run_forever_retries_after_connection_error():
    pipeline=MagicMock()
    consumer = RabbitMqTrafficConsumer("localhost", pipeline)
    call_count = 0

    def fake_connect_and_consume():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("bağlantı koptu")
        consumer._stopping = True  # ikinci denemede döngüden çıkıyor

    with patch.object(consumer, "_connect_and_consume", side_effect=fake_connect_and_consume):
        with patch("app.messaging.rabbitmq_consumer.time.sleep") as mock_sleep:
            consumer.run_forever()

    assert call_count == 2
    mock_sleep.assert_called_once_with(RECONNECT_DELAY_SECONDS)

def test_stop_closes_open_connection():
    pipeline = MagicMock()
    consumer = RabbitMqTrafficConsumer("localhost", pipeline)
    mock_connection = MagicMock()
    mock_connection.is_open = True
    consumer._connection = mock_connection

    consumer.stop()

    assert consumer._stopping is True
    mock_connection.close.assert_called_once()


def test_stop_does_nothing_if_no_connection_yet():
    pipeline = MagicMock()
    consumer = RabbitMqTrafficConsumer("localhost", pipeline)

    consumer.stop()  # _connection hala None, hata fırlatmamalı

    assert consumer._stopping is True