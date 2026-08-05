"""
OpenSight Analiz Servisi (FastAPI) - RabbitMQ'den gelen trafik olaylarını tüketiyor,
Redis'te rolling pencere tutuyor, RollingZScoreDetector + BehavioralAnomalyDetector
ile paralel skorluyor, CorrelationEngine'de birleştiriyor ve ExplanationGenerator ile
açıklama üretip OpenSight.Api'ye yazıyor
"""
from __future__ import annotations

import os
import threading

from fastapi import FastAPI
from pydantic import BaseModel
from redis import Redis

from app.messaging.backend_client import BackendClient
from app.messaging.rabbitmq_consumer import RabbitMqTrafficConsumer
from app.services.anomaly_pipeline import AnomalyPipeline
from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.cold_start import ColdStartManager
from app.services.correlation_engine import CorrelationEngine
from app.services.explanation_generator import ExplanationGenerator
from app.services.performance_detector import RollingZScoreDetector
from app.services.traffic_window import ClientTrafficWindow

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
COLD_START_SECONDS = int(os.environ.get("COLD_START_SECONDS", "90"))
BACKEND_URL = os.environ.get("OPENSIGHT_API_URL", "http://localhost:8080")

app = FastAPI(title="OpenSight Analiz Servisi", version="0.1.0")

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

performance_detector = RollingZScoreDetector(redis_client, window_size=50, threshold=3.2)
behavioral_detector = BehavioralAnomalyDetector(contamination=0.05)
traffic_window = ClientTrafficWindow(redis_client)
cold_start = ColdStartManager(redis_client, behavioral_detector, cold_start_seconds=COLD_START_SECONDS)
correlation_engine = CorrelationEngine(window_seconds=30 * 60)
explanation_generator = ExplanationGenerator()
backend_client = BackendClient(BACKEND_URL)

anomaly_pipeline = AnomalyPipeline(
    performance_detector, behavioral_detector, traffic_window, cold_start, correlation_engine, backend_client
)
traffic_consumer = RabbitMqTrafficConsumer(RABBITMQ_HOST, anomaly_pipeline, port=RABBITMQ_PORT)
_consumer_thread: threading.Thread | None = None


@app.on_event("startup")
def start_traffic_consumer() -> None:
    """backend'i ısıtıyor, sonra RabbitMQ consumer'ı arka plan thread'inde başlatıyor - API'yi bloklamıyor"""
    backend_client.warmup()
    global _consumer_thread
    _consumer_thread = threading.Thread(target=traffic_consumer.run_forever, daemon=True)
    _consumer_thread.start()


@app.on_event("shutdown")
def stop_traffic_consumer() -> None:
    traffic_consumer.stop()


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "opensight-analysis"}


class LatencySample(BaseModel):
    client_id: str
    latency_ms: float


@app.post("/debug/score-latency")
def score_latency(sample: LatencySample) -> dict:
    """gerçek RabbitMQ akışı olmadan rolling z-score'u test etmek için"""
    result = performance_detector.update_and_score(sample.client_id, sample.latency_ms)
    return {
        "z_score": result.z_score,
        "is_anomaly": result.is_anomaly,
        "mean": result.mean,
        "std": result.std,
    }