"""
AnomalyPipeline'ın orkestrasyon mantığını (backend'e yazma, korelasyon) mock'lanmış
detector'lar ve BackendClient ile doğruluyor - gerçek Redis/HTTP gerektirmiyor
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.anomaly_pipeline import AnomalyPipeline
from app.services.behavioral_detector import BehavioralScoreResult
from app.services.correlation_engine import CorrelationEngine
from app.services.performance_detector import ZScoreResult


def _make_pipeline(perf_is_anomaly=False, behavioral_is_anomaly=False, cold_start_ready=True):
    performance_detector = MagicMock()
    performance_detector.update_and_score.return_value = ZScoreResult(
        z_score=5.0 if perf_is_anomaly else 0.5, is_anomaly=perf_is_anomaly, mean=50.0, std=2.0
    )

    behavioral_detector = MagicMock()
    behavioral_detector.score.return_value = BehavioralScoreResult(
        anomaly_score=0.9 if behavioral_is_anomaly else 0.1, is_anomaly=behavioral_is_anomaly
    )

    traffic_window = MagicMock()
    traffic_window.record.return_value = [1.0, 0.5, 40.0]

    cold_start = MagicMock()
    cold_start.is_ready.return_value = cold_start_ready

    correlation_engine = CorrelationEngine(window_seconds=1800)
    backend_client = MagicMock()

    pipeline = AnomalyPipeline(
        performance_detector, behavioral_detector, traffic_window, cold_start, correlation_engine, backend_client
    )
    return pipeline, backend_client


def test_no_anomaly_does_not_post_alert():
    pipeline, backend_client = _make_pipeline()

    pipeline.process("client_a", "/v1/accounts", 50, timestamp=1000.0)

    backend_client.post_alert.assert_not_called()
    backend_client.post_correlation.assert_not_called()


def test_performance_anomaly_posts_alert_but_not_correlation():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True)
    backend_client.post_alert.return_value = "alert-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    backend_client.post_alert.assert_called_once_with(
        "client_a", "Performans", "Orta", z_score=5.0, related_endpoint="/v1/accounts"
    )
    backend_client.post_correlation.assert_not_called()


def test_behavioral_detection_skipped_during_cold_start():
    pipeline, backend_client = _make_pipeline(behavioral_is_anomaly=True, cold_start_ready=False)

    pipeline.process("client_a", "/v1/accounts", 50, timestamp=1000.0)

    pipeline.behavioral_detector.score.assert_not_called()
    backend_client.post_alert.assert_not_called()


def test_overlapping_anomalies_post_correlation():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, behavioral_is_anomaly=True)
    backend_client.post_alert.side_effect = ["perf-1", "beh-1"]
    backend_client.post_correlation.return_value = "corr-1"

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    assert backend_client.post_alert.call_count == 2
    backend_client.post_correlation.assert_called_once_with("perf-1", "beh-1")


def test_failed_alert_post_skips_correlation_attempt():
    pipeline, backend_client = _make_pipeline(perf_is_anomaly=True, behavioral_is_anomaly=True)
    backend_client.post_alert.return_value = None  # backend'e ulaşılamadı

    pipeline.process("client_a", "/v1/accounts", 5000, timestamp=1000.0)

    backend_client.post_correlation.assert_not_called()
