"""
AnomalyPipeline: tek bir trafik olayını performans (z-score) ve davranışsal (Isolation
Forest) tespitinden geçiriyor, anomali bulunursa backend'e alarm yazıyor,
CorrelationEngine ile eş zamanlı anomalileri birleştirip birleşik olayı da backend'e yazıyor
"""
from __future__ import annotations

import logging

import threading
from datetime import datetime, timezone

from app.messaging.backend_client import BackendClient
from app.services.behavioral_detector import BehavioralAnomalyDetector
from app.services.cold_start import ColdStartManager
from app.services.correlation_engine import CorrelationEngine, PendingAlert
from app.services.explanation_generator import ExplanationGenerator
from app.services.performance_detector import RollingZScoreDetector
from app.services.threshold_settings import ThresholdSettingsService
from app.services.traffic_window import ClientTrafficWindow
logger = logging.getLogger("opensight.anomaly_pipeline")


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
        explanation_generator: ExplanationGenerator | None = None,
    ):
        self.performance_detector = performance_detector
        self.behavioral_detector = behavioral_detector
        self.traffic_window = traffic_window
        self.cold_start = cold_start
        self.correlation_engine = correlation_engine
        self.backend_client = backend_client
        self.threshold_settings = threshold_settings
        self.explanation_generator = explanation_generator

    def process(self, client_id: str, endpoint: str, latency_ms: float, timestamp: float) -> None:
        """tek bir trafik olayını işliyor - tespit, korelasyon ve backend'e yazma burada birleşiyor"""
        perf_result = self.performance_detector.update_and_score(client_id, latency_ms)
        feature_vector = self.traffic_window.record(client_id, endpoint, latency_ms, timestamp)
        self.cold_start.handle(feature_vector)

        pending: list[tuple[str, str]] = []

        # feature_vector[0], ClientTrafficWindow'un saniyedeki istek sayisi olarak hesapladigi
        # ham deger (req/s) - backend'deki request_rate_pct alani onceden hep bos gidiyordu,
        # burada baglaniyor.
        request_rate = feature_vector[0]

        if perf_result.is_anomaly:
            severity = severity_for_zscore(perf_result.z_score)
            description = self._fallback_description(client_id, "Performans", severity)
            post_kwargs = {
                "z_score": perf_result.z_score,
                "related_endpoint": endpoint,
                "request_rate_pct": request_rate,
            }
            if description is not None:
                post_kwargs["description"] = description
            alert_id = self.backend_client.post_alert(client_id, "Performans", severity, **post_kwargs)
            if alert_id:
                pending.append(("Performans", alert_id))
                if self.threshold_settings:
                    self.threshold_settings.record_alert("Performans")
                self._start_explanation_refinement(
                    alert_id, client_id, "Performans", severity, description, {"z_score": perf_result.z_score}
                )

        if self.cold_start.is_ready():
            behavioral_result = self.behavioral_detector.score(feature_vector)
            if behavioral_result.is_anomaly:
                severity = severity_for_anomaly_score(behavioral_result.anomaly_score)
                description = self._fallback_description(client_id, "Davranışsal", severity)
                post_kwargs = {
                    "anomaly_score": behavioral_result.anomaly_score,
                    "related_endpoint": endpoint,
                    "request_rate_pct": request_rate,
                }
                if description is not None:
                    post_kwargs["description"] = description
                alert_id = self.backend_client.post_alert(client_id, "Davranışsal", severity, **post_kwargs)
                if alert_id:
                    pending.append(("Davranışsal", alert_id))
                    if self.threshold_settings:
                        self.threshold_settings.record_alert("Davranışsal")
                    self._start_explanation_refinement(
                        alert_id, client_id,"Davranışsal", severity, description,
                        {"anomaly_score": behavioral_result.anomaly_score},
                    )

        alert_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        for alert_type, alert_id in pending:
            correlation = self.correlation_engine.register_alert(PendingAlert(alert_id, client_id, alert_type, alert_time))
            if correlation is not None:
                self.backend_client.post_correlation(correlation.performance_alert_id, correlation.behavioral_alert_id)

    def _fallback_description(self, client_id: str, alert_type: str, severity: str) -> str | None:
        """explanation_generator taniminmissa aninda (I/O olmadan) kural tabanli aciklamayi uretiyor"""
        if self.explanation_generator is None:
            return None
        return self.explanation_generator.fallback_template(client_id, alert_type, severity)

    def _start_explanation_refinement(
        self, alert_id: str, client_id: str, alert_type: str, severity: str, fallback_text: str | None, metrics: dict
    ) -> None:
        """ollama'dan daha iyi bir aciklama gelirse alert'i arka planda gunceller - ayri bir thread'de
        calisir, ana RabbitMQ tuketim akisini asla bloklamaz/yavaslatmaz"""
        if self.explanation_generator is None:
            return
        thread = threading.Thread(
            target=self._refine_explanation,
            args=(alert_id, client_id, alert_type, severity, fallback_text, metrics),
            daemon=True,
        )
        thread.start()

    def _refine_explanation(
        self, alert_id: str, client_id: str, alert_type: str, severity: str, fallback_text: str | None, metrics: dict
    ) -> None:
        """arka plan thread'inde calisan is - burada olusan hiçbir hata ana pipeline'a sizmiyor"""
        try:
            explanation = self.explanation_generator.generate_explanation(client_id, alert_type, severity, metrics)
            if explanation and explanation != fallback_text:
                self.backend_client.patch_alert_description(alert_id, explanation)
            else:
                logger.info(
                    "Ollama'dan sablon disi bir aciklama gelmedi (alert=%s) - fallback aciklama kaliyor", alert_id
                )
        except Exception:
            logger.exception("arka planda aciklama zenginlestirme basarisiz oldu (alert=%s)", alert_id)
