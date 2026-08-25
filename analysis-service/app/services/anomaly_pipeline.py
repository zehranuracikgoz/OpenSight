"""
AnomalyPipeline: tek bir trafik olayını performans (z-score) ve davranışsal (Isolation
Forest) tespitinden geçiriyor, anomali bulunursa backend'e alarm yazıyor,
CorrelationEngine ile eş zamanlı anomalileri birleştirip birleşik olayı da backend'e yazıyor
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.messaging.backend_client import BackendClient
from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.cold_start import ColdStartManager
from app.services.correlation_engine import CorrelationEngine, PendingAlert
from app.services.performance_detector import RollingZScoreDetector
from app.services.threshold_settings import ThresholdSettingsService
from app.services.traffic_window import ClientTrafficWindow


def severity_for_zscore(z_score: float) -> str:
    if abs(z_score) >= 6.0:
        return "Yüksek"
    if abs(z_score) >= 4.0:
        return "Orta"
    return "Düşük"


def severity_for_anomaly_score(anomaly_score: float) -> str:
    if anomaly_score >= 0.8:
        return "Yüksek"
    if anomaly_score >= 0.6:
        return "Orta"
    return "Düşük"


class AnomalyPipeline:
    def __init__(
        self,
        performance_detector: RollingZScoreDetector,
        behavioral_detector: BehavioralAnomalyDetector,
        traffic_window: ClientTrafficWindow,
        cold_start: ColdStartManager,
        correlation_engine: CorrelationEngine,
        backend_client: BackendClient,
        threshold_settings: ThresholdSettingsService | None = None,
    ):
        self.performance_detector = performance_detector
        self.behavioral_detector = behavioral_detector
        self.traffic_window = traffic_window
        self.cold_start = cold_start
        self.correlation_engine = correlation_engine
        self.backend_client = backend_client
        self.threshold_settings = threshold_settings

    def process(self, client_id: str, endpoint: str, latency_ms: float, timestamp: float) -> None:
        """tek bir trafik olayını işliyor - tespit, korelasyon ve backend'e yazma burada birleşiyor"""
        perf_result = self.performance_detector.update_and_score(client_id, latency_ms)
        feature_vector = self.traffic_window.record(client_id, endpoint, latency_ms, timestamp)
        self.cold_start.handle(feature_vector)

        pending: list[tuple[str, str]] = []

        if perf_result.is_anomaly:
            alert_id = self.backend_client.post_alert(
                client_id, "Performans", severity_for_zscore(perf_result.z_score),
                z_score=perf_result.z_score, related_endpoint=endpoint,
            )
            if alert_id:
                pending.append(("Performans", alert_id))
                if self.threshold_settings:
                    self.threshold_settings.record_alert("Performans")

        if self.cold_start.is_ready():
            behavioral_result = self.behavioral_detector.score(feature_vector)
            if behavioral_result.is_anomaly:
                alert_id = self.backend_client.post_alert(
                    client_id, "Davranışsal", severity_for_anomaly_score(behavioral_result.anomaly_score),
                    anomaly_score=behavioral_result.anomaly_score, related_endpoint=endpoint,
                )
                if alert_id:
                    pending.append(("Davranışsal", alert_id))
                    if self.threshold_settings:
                        self.threshold_settings.record_alert("Davranışsal")

        alert_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        for alert_type, alert_id in pending:
            correlation = self.correlation_engine.register_alert(PendingAlert(alert_id, client_id, alert_type, alert_time))
            if correlation is not None:
                self.backend_client.post_correlation(correlation.performance_alert_id, correlation.behavioral_alert_id)
