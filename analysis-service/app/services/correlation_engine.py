"""
CorrelationEngine: aynı istemci için eş zamanlı tetiklenen performans + davranışsal
anomaliyi birleşik bir olay olarak işaretliyor - zaman penceresi varsayılan 30 dakika
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class PendingAlert:
    alert_id: str
    client_id: str
    alert_type: str  # "Performans" | "Davranışsal"
    timestamp: datetime


@dataclass
class CorrelationResult:
    performance_alert_id: str
    behavioral_alert_id: str
    client_id: str


class CorrelationEngine:
    def __init__(self, window_seconds: int = 30 * 60):
        self.window_seconds = window_seconds
        self._pending: dict[str, list[PendingAlert]] = {}

    def register_alert(self, alert: PendingAlert) -> CorrelationResult | None:
        """
        yeni alert'i kaydediyor, aynı istemci için pencere içinde zıt türde bekleyen
        bir alert varsa korelasyon üretiyor, yoksa none dönüyor
        """
        bucket = self._pending.setdefault(alert.client_id, [])

        # pencere dışına çıkmış eski kayıtları temizle
        cutoff = alert.timestamp - timedelta(seconds=self.window_seconds)
        bucket[:] = [a for a in bucket if a.timestamp >= cutoff]

        match = next((a for a in bucket if a.alert_type != alert.alert_type), None)
        if match is not None:
            bucket.remove(match)
            perf_id = alert.alert_id if alert.alert_type == "Performans" else match.alert_id
            beh_id = alert.alert_id if alert.alert_type == "Davranışsal" else match.alert_id
            return CorrelationResult(performance_alert_id=perf_id, behavioral_alert_id=beh_id, client_id=alert.client_id)

        bucket.append(alert)
        return None