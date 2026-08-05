"""
RabbitMqTrafficConsumer: backend'in "opensight.traffic" exchange'ini dinliyor, gelen
TrafficEvent mesajlarını performans + davranışsal tespite besliyor, bağlantı koparsa
yeniden dener. TrafficEventDto'da timestamp olmadığı için mesajın varış anı kullanılıyor.
"""
from __future__ import annotations

import json
import logging
import time

import pika

from app.services.cold_start import ColdStartManager
from app.services.performance_detector import RollingZScoreDetector
from app.services.traffic_window import ClientTrafficWindow

logger = logging.getLogger("opensight.consumer")

EXCHANGE_NAME = "opensight.traffic"
RECONNECT_DELAY_SECONDS = 5


class RabbitMqTrafficConsumer:
    def __init__(
        self,
        host: str,
        performance_detector: RollingZScoreDetector,
        traffic_window: ClientTrafficWindow,
        cold_start: ColdStartManager,
        port: int = 5672,
    ):
        self.host = host
        self.port = port
        self.performance_detector = performance_detector
        self.traffic_window = traffic_window
        self.cold_start = cold_start
        self._stopping = False
        self._connection: pika.BlockingConnection | None = None

    def stop(self) -> None:
        self._stopping = True
        if self._connection is not None and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass

    def run_forever(self) -> None:
        """bağlantı koparsa da vazgeçmeden yeniden dener - arka plan thread'inde çalıştırılmalı"""
        while not self._stopping:
            try:
                self._connect_and_consume()
            except Exception as exc:
                if self._stopping:
                    break
                logger.warning(
                    "RabbitMQ bağlantısı kurulamadı/koptu (%s), %ss sonra tekrar denenecek",
                    exc, RECONNECT_DELAY_SECONDS,
                )
                time.sleep(RECONNECT_DELAY_SECONDS)

    def _connect_and_consume(self) -> None:
        self._connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host, port=self.port, heartbeat=0)
        )
        try:
            channel = self._connection.channel()
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)
            queue = channel.queue_declare(queue="", exclusive=True)
            queue_name = queue.method.queue
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name)

            logger.info("RabbitMQ'ya bağlandı (%s), %s exchange'i dinleniyor", self.host, EXCHANGE_NAME)
            channel.basic_consume(queue=queue_name, on_message_callback=self._on_message, auto_ack=True)
            channel.start_consuming()
        finally:
            if self._connection.is_open:
                self._connection.close()

    def _on_message(self, ch, method, properties, body: bytes) -> None:
        try:
            payload = json.loads(body)
            client_id = payload["ClientId"]
            endpoint = payload["Endpoint"]
            latency_ms = payload["LatencyMs"]
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
            logger.warning("parse edilemeyen trafik mesajı atlandı (%s): %r", exc, body)
            return

        now = time.time()
        self.performance_detector.update_and_score(client_id, latency_ms)
        feature_vector = self.traffic_window.record(client_id, endpoint, latency_ms, now)
        self.cold_start.handle(feature_vector)
