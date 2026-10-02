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

DEFAULT_ALERT_COOLDOWN_SECONDS = 300.0


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
        alert_cooldown_seconds: float = DEFAULT_ALERT_COOLDOWN_SECONDS,
    ):
        self.performance_detector = performance_detector
        self.behavioral_detector = behavioral_detector
        self.traffic_window = traffic_window
        self.cold_start = cold_start
        self.correlation_engine = correlation_engine
        self.backend_client = backend_client
        self.threshold_settings = threshold_settings
        self.explanation_generator = explanation_generator
        self.alert_cooldown_seconds = alert_cooldown_seconds
        # (istemci, alarm türü) -> son alarmın zamanı; aynı tür alarm cooldown süresince tekrar yazılmıyor
        self._last_alert_at: dict[tuple[str, str], float] = {}

    def _in_cooldown(self, client_id: str, alert_type: str, timestamp: float) -> bool:
        last = self._last_alert_at.get((client_id, alert_type))
        return last is not None and timestamp - last < self.alert_cooldown_seconds

    def process(self, client_id: str, endpoint: str, latency_ms: float, timestamp: float) -> None:
        """tek bir trafik olayını işliyor - tespit, korelasyon ve backend'e yazma burada birleşiyor"""
        perf_result = self.performance_detector.update_and_score(client_id, latency_ms)
        feature_vector = self.traffic_window.record(client_id, endpoint, latency_ms, timestamp)
        self.cold_start.handle(client_id, feature_vector, timestamp)

        # (tür, alert_id, açıklama, kısa özet)
        pending: list[tuple[str, str, str, str]] = []

        # feature_vector[0], ClientTrafficWindow'un saniyedeki istek sayisi olarak hesapladigi
        # ham deger (req/s) - backend'deki request_rate_pct alani onceden hep bos gidiyordu,
        # burada baglaniyor.
        request_rate = feature_vector[0]

        # cooldown türe göre ayrı - performans beklerken gelen davranışsal alarm yine yazılıyor
        if perf_result.is_anomaly and not self._in_cooldown(client_id, "Performans", timestamp):
            severity = severity_for_zscore(perf_result.z_score)
            metrics = self._performance_metrics(perf_result, latency_ms, endpoint)
            description = self._fallback_description(client_id, "Performans", severity, metrics)
            post_kwargs = {
                "z_score": perf_result.z_score,
                "related_endpoint": endpoint,
                "request_rate_pct": request_rate,
            }
            if description is not None:
                post_kwargs["description"] = description
            alert_id = self.backend_client.post_alert(client_id, "Performans", severity, **post_kwargs)
            if alert_id:
                self._last_alert_at[(client_id, "Performans")] = timestamp
                pending.append(("Performans", alert_id, description or "", self._summary("Performans", metrics)))
                if self.threshold_settings:
                    self.threshold_settings.record_alert("Performans")
                self._start_explanation_refinement(alert_id, client_id, "Performans", severity, description, metrics)

        if self.cold_start.is_ready():
            behavioral_result = self.behavioral_detector.score(feature_vector)
            if behavioral_result.is_anomaly and not self._in_cooldown(client_id, "Davranışsal", timestamp):
                severity = severity_for_anomaly_score(behavioral_result.anomaly_score)
                metrics = self._behavioral_metrics(client_id, behavioral_result, feature_vector, timestamp)
                description = self._fallback_description(client_id, "Davranışsal", severity, metrics)
                post_kwargs = {
                    "anomaly_score": behavioral_result.anomaly_score,
                    # davranışsal alarmda en sık endpoint gösteriliyor
                    "related_endpoint": metrics.get("top_endpoint") or endpoint,
                    "request_rate_pct": request_rate,
                }
                if description is not None:
                    post_kwargs["description"] = description
                alert_id = self.backend_client.post_alert(client_id, "Davranışsal", severity, **post_kwargs)
                if alert_id:
                    self._last_alert_at[(client_id, "Davranışsal")] = timestamp
                    pending.append(("Davranışsal", alert_id, description or "", self._summary("Davranışsal", metrics)))
                    if self.threshold_settings:
                        self.threshold_settings.record_alert("Davranışsal")
                    self._start_explanation_refinement(
                        alert_id, client_id, "Davranışsal", severity, description, metrics
                    )

        alert_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        for alert_type, alert_id, description, summary in pending:
            alert = PendingAlert(alert_id, client_id, alert_type, alert_time, description=description, summary=summary)
            correlation = self.correlation_engine.register_alert(alert)
            if correlation is not None:
                correlation_id = self.backend_client.post_correlation(
                    correlation.performance_alert_id, correlation.behavioral_alert_id
                )
                if correlation_id:
                    self._describe_correlation(correlation)

    def _performance_metrics(self, perf_result, latency_ms: float, endpoint: str) -> dict:
        return {
            "z_score": perf_result.z_score,
            "latency_ms": latency_ms,
            "window_mean": perf_result.mean,
            "sample_count": perf_result.sample_count,
            "endpoint": endpoint,
        }
    def _behavioral_metrics(self, client_id: str, behavioral_result, feature_vector: list[float], timestamp: float) -> dict:
        metrics ={
            "anomaly_score": behavioral_result.anomaly_score,
            "istek_orani": feature_vector[0],
            "en_sik_endpoint_payi": feature_vector[1],
            "ortalama_gecikme": feature_vector[2],
            "baseline_median": self.behavioral_detector.baseline_median,
        }
        metrics["top_endpoint"] = self._top_endpoint_name(client_id, timestamp)
        return metrics

    def _top_endpoint_name(self, client_id: str, timestamp: float) -> str | None:
        """en sık endpoint in adı, Redis hatasında none"""
        try:
            top = self.traffic_window.top_endpoint(client_id, now=timestamp)
            return top[0] if top else None
        except Exception:
            return None

    def _summary(self, alert_type: str, metrics: dict) -> str:
        if self.explanation_generator is None:
            return ""
        return self.explanation_generator.summary(alert_type, metrics)

    def _describe_correlation(self, correlation) -> None:
        """korelasyon cümlesini iki alarmın açıklamasına ekliyor"""
        if self.explanation_generator is None or not correlation.performance_summary:
            return
        combined=self.explanation_generator.combined_explanation(correlation.performance_summary)
        for alert_id, own in (
            (correlation.performance_alert_id, correlation.performance_description),
            (correlation.behavioral_alert_id, correlation.behavioral_description),
        ):
            text = f"{own}\nKorelasyon: {combined}" if own else f"Korelasyon: {combined}"
            self.backend_client.patch_alert_description(alert_id, text)

    def _fallback_description(self, client_id: str, alert_type: str, severity: str, metrics: dict) -> str | None:
        """explanation_generator taniminmissa aninda (I/O olmadan) kural tabanli aciklamayi uretiyor"""
        if self.explanation_generator is None:
            return None
        return self.explanation_generator.fallback_template(client_id, alert_type, severity, metrics)

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
