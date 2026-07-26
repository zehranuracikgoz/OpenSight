"""
OpenSight Analiz Servisi (FastAPI) - RabbitMQ'den gelen trafik olaylarını tüketiyor,
Redis'te rolling pencere tutuyor, RollingZScoreDetector +BehavioralAnomalyDetector
ile paralel skorlar, CorrelationEngine'de birleştiriyor ve ExplanationGenerator ile
açıklama üretip OpenSight.Api'ye yazıyor
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.correlation_engine import CorrelationEngine
from app.services.explanation_generator import ExplanationGenerator
from app.services.performance_detector import RollingZScoreDetector

app = FastAPI(title="OpenSight Analiz Servisi", version="0.1.0")

performance_detector = RollingZScoreDetector(window_size=50, threshold=3.2)
behavioral_detector = BehavioralAnomalyDetector(contamination=0.05)
correlation_engine = CorrelationEngine(window_seconds=30 * 60)
explanation_generator = ExplanationGenerator()


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "opensight-analysis"}


class LatencySample(BaseModel):
    client_id: str
    latency_ms: float


@app.post("/debug/score-latency")
def score_latency(sample: LatencySample) -> dict:
    """gerçek RabbitMQ akışı olmadan rolling z-score'u test etmek için (Sprint 1 doğrulama)"""
    result = performance_detector.update_and_score(sample.client_id, sample.latency_ms)
    return {
        "z_score": result.z_score,
        "is_anomaly": result.is_anomaly,
        "mean": result.mean,
        "std": result.std,
    }