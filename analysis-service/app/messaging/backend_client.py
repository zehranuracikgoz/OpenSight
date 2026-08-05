"""
BackendClient: tespit edilen alarmları ve korelasyon olaylarını backend'in REST API'sine
(OpenSight.Api) HTTP ile yazıyor - analiz servisi SQL Server'a doğrudan bağlanmıyor,
tek veri erişim yolu backend/EF Core üzerinden kalıyor. Backend'e ulaşılamazsa
istisna fırlatmıyor, sadece logluyor ve None dönüyor.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("opensight.backend_client")


class BackendClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def warmup(self, timeout: float = 15.0) -> bool:
        """backend'e bir health-check isteği atıp soğuk başlangıç gecikmesini burada karşılıyor -
        consumer gerçek trafiği işlemeye başlamadan önce çağrılmalı, ilk gerçek alarm isteği
        zaman aşımına uğramasın diye"""
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=timeout)
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("backend ısıtma isteği başarısız (%s) - ilk gerçek istek daha yavaş olabilir", exc)
            return False

    def post_alert(
        self,
        client_id: str,
        alert_type: str,
        severity: str,
        description: str | None = None,
        z_score: float | None = None,
        anomaly_score: float | None = None,
        request_rate_pct: float | None = None,
        related_endpoint: str | None = None,
    ) -> str | None:
        """yeni alarmı backend'e yazıyor, oluşan alertId'yi döndürüyor - başarısız olursa None"""
        payload = {
            "clientId": client_id,
            "type": alert_type,
            "severity": severity,
            "description": description,
            "zScore": z_score,
            "anomalyScore": anomaly_score,
            "requestRatePct": request_rate_pct,
            "relatedEndpoint": related_endpoint,
        }
        try:
            response = httpx.post(f"{self.base_url}/api/alerts", json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("alertId")
        except httpx.HTTPError as exc:
            logger.warning("backend'e alarm yazılamadı (client=%s, tür=%s): %s", client_id, alert_type, exc)
            return None

    def post_correlation(self, performance_alert_id: str, behavioral_alert_id: str) -> str | None:
        """iki alarmı backend'de tek bir korelasyon olayı olarak birleştiriyor"""
        payload = {"performanceAlertId": performance_alert_id, "behavioralAlertId": behavioral_alert_id}
        try:
            response = httpx.post(f"{self.base_url}/api/alerts/correlations", json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json().get("correlationId")
        except httpx.HTTPError as exc:
            logger.warning(
                "backend'e korelasyon yazılamadı (perf=%s, davranışsal=%s): %s",
                performance_alert_id, behavioral_alert_id, exc,
            )
            return None
